import boto3

def set_mfa_optional():
    client = boto3.client('cognito-idp', region_name='us-east-1')
    user_pool_id = 'us-east-1_Nc0OZJRgL'
    
    try:
        response = client.set_user_pool_mfa_config(
            UserPoolId=user_pool_id,
            SoftwareTokenMfaConfiguration={
                'Enabled': True
            },
            MfaConfiguration='OPTIONAL'
        )
        print("Success: MFA set to OPTIONAL")
        print(response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    set_mfa_optional()
