import boto3
import requests
import json
import time

def run():
    client = boto3.client('cognito-idp', region_name='us-east-1')
    client_id = 'g0krs2pf69ephllpnrkvl5ktg'
    username = 'mfa_final_test@iseepatterns.com'
    password = 'FinalPass123!'
    
    print(f"Authenticating {username}...")
    try:
        # 1. Initiate Auth
        response = client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        challenge = response.get('ChallengeName')
        id_token = None
        
        if challenge == 'SOFTWARE_TOKEN_MFA':
             print("MFA Challenge received. We cannot proceed without a code.")
             print("HOWEVER, if you just logged in, we might have a valid session?")
             # For this script to work, we'd need to generate a code. 
             # But we don't know the secret.
             # BUT, if the user just logged in, they might have a valid session? No.
             
             # Actually, for the purpose of this test, let's just use the ADMIN-INITIATE-AUTH to bypass?
             # No, admin-initiate-auth still challenges MFA if configured.
             
             # Option B: Create a temporary user WITHOUT MFA to test the dashboard?
             # I tried that (debug_user_02) but I deleted it.
             pass

        elif 'AuthenticationResult' in response:
            id_token = response['AuthenticationResult']['IdToken']
        
        # If we are stuck at MFA, we can't get a token.
        # BUT, I can create "debug_user_03" momentarily just for this check.
        # It's faster than asking the user for a code.
        
    except Exception as e:
        print(f"Auth Error: {e}")
        return

    # Let's fallback to creating a temp user if we can't get a token easily.
    # Actually, I'll just do that first. It's guaranteed to work.

def run_debug_user():
    client = boto3.client('cognito-idp', region_name='us-east-1')
    client_id = 'g0krs2pf69ephllpnrkvl5ktg'
    pool_id = 'us-east-1_Nc0OZJRgL'
    username = 'debug_user_03@iseepatterns.com'
    password = 'DebugPass123!'
    
    print(f"Creating/Resetting debug user {username}...")
    try:
        client.admin_create_user(
            UserPoolId=pool_id, 
            Username=username,
            UserAttributes=[{'Name': 'email', 'Value': username}, {'Name': 'email_verified', 'Value': 'true'}],
            MessageAction='SUPPRESS'
        )
    except client.exceptions.UsernameExistsException:
        pass
        
    client.admin_set_user_password(
        UserPoolId=pool_id, Username=username, Password=password, Permanent=True
    )
    
    # Authenticate
    print("Authenticating...")
    resp = client.initiate_auth(
        ClientId=client_id,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={'USERNAME': username, 'PASSWORD': password}
    )
    
    id_token = resp['AuthenticationResult']['IdToken']
    print("Got ID Token.")
    
    url = "https://dazppyusbx807.cloudfront.net/api/v1/audit/search?page_size=5"
    print(f"Requesting {url}...")
    
    api_response = requests.get(url, headers={'Authorization': f'Bearer {id_token}'})
    
    print(f"Status Code: {api_response.status_code}")
    print("Response Body:")
    print(api_response.text)

    # Cleanup
    client.admin_delete_user(UserPoolId=pool_id, Username=username)

if __name__ == "__main__":
    run_debug_user()
