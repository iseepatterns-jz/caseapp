import boto3

def add_api_behavior():
    client = boto3.client('cloudfront')
    dist_id = 'E3QOTF0KDJPEW8'
    
    # Get current config
    try:
        dist_config_response = client.get_distribution_config(Id=dist_id)
        config = dist_config_response['DistributionConfig']
        etag = dist_config_response['ETag']
        
        # Define API Origin
        api_origin_id = 'API-ALB'
        api_domain = 'courtc-backe-tr6bfujbdq6j-1007266332.us-east-1.elb.amazonaws.com'
        
        # Check if origin exists
        origins = config['Origins']
        origin_exists = any(o['Id'] == api_origin_id for o in origins['Items'])
        
        if not origin_exists:
            new_origin = {
                'Id': api_origin_id,
                'DomainName': api_domain,
                'CustomOriginConfig': {
                    'HTTPPort': 80,
                    'HTTPSPort': 443,
                    'OriginProtocolPolicy': 'http-only',
                    'OriginSslProtocols': {
                        'Quantity': 1,
                        'Items': ['TLSv1.2']
                    },
                    'OriginReadTimeout': 30,
                    'OriginKeepaliveTimeout': 5
                },
                'ConnectionAttempts': 3,
                'ConnectionTimeout': 10,
                'OriginPath': ''  # ALB root
            }
            origins['Quantity'] += 1
            origins['Items'].append(new_origin)
            print("Added API Origin")

        # Add Cache Behavior
        cache_behaviors = config.get('CacheBehaviors', {'Quantity': 0, 'Items': []})
        
        # Check if behavior exists
        behavior_exists = any(b['PathPattern'] == '/api/*' for b in cache_behaviors.get('Items', []))
        
        if not behavior_exists:
            new_behavior = {
                'PathPattern': '/api/*',
                'TargetOriginId': api_origin_id,
                'ViewerProtocolPolicy': 'redirect-to-https',
                'AllowedMethods': {
                    'Quantity': 7,
                    'Items': ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'OPTIONS', 'DELETE'],
                    'CachedMethods': {
                        'Quantity': 2,
                        'Items': ['GET', 'HEAD']
                    }
                },
                'SmoothStreaming': False,
                'Compress': True,
                'LambdaFunctionAssociations': {'Quantity': 0},
                'FunctionAssociations': {'Quantity': 0},
                'FieldLevelEncryptionId': '',
                'ForwardedValues': {
                    'QueryString': True,
                    'Cookies': {
                        'Forward': 'all'
                    },
                    'Headers': {
                        'Quantity': 3,
                        'Items': ['Authorization', 'Host', 'Origin'] 
                    },
                    'QueryStringCacheKeys': {'Quantity': 0}
                },
                'MinTTL': 0,
                'DefaultTTL': 0,
                'MaxTTL': 0
            }
            
            if cache_behaviors['Quantity'] == 0:
                 cache_behaviors['Items'] = [new_behavior]
            else:
                 cache_behaviors['Items'].append(new_behavior)
            
            cache_behaviors['Quantity'] += 1
            config['CacheBehaviors'] = cache_behaviors
            print("Added API Cache Behavior")
            
            # Update Distribution
            client.update_distribution(
                Id=dist_id,
                DistributionConfig=config,
                IfMatch=etag
            )
            print("Distribution Updated Successfully")
        else:
             print("API Behavior already exists")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_api_behavior()
