import boto3
import sys

def create_user():
    client = boto3.client('cognito-idp', region_name='us-east-1')
    pool_id = 'us-east-1_Nc0OZJRgL'
    # schema requires username to be an email
    username = 'mfa_final_test@iseepatterns.com'
    email = 'mfa_final_test@iseepatterns.com'
    
    print(f"Creating user {username} in pool {pool_id}...")
    
    try:
        response = client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            TemporaryPassword='FinalPass123!',
            MessageAction='SUPPRESS'
        )
        print("User created successfully!")
        
        # Immediately set permanent password to skip force-change
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password='FinalPass123!',
            Permanent=True
        )
        print("Password set to 'FinalPass123!' (Permanent)")
        
    except client.exceptions.UsernameExistsException:
        print("User already exists. Updating password...")
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password='FinalPass123!',
            Permanent=True
        )
        print("Password updated to 'FinalPass123!' (Permanent)")
    except Exception as e:
        print(f"Error creating user: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_user()
