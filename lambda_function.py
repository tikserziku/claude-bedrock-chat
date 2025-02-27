import json
import boto3
from botocore.config import Config

def lambda_handler(event, context):
    try:
        # Parse request
        request_body = event.get('body', '{}')
        if isinstance(request_body, str):
            request_body = json.loads(request_body)
        
        current_prompt = request_body.get('prompt', '')
        image_data = request_body.get('image')

        # Initialize Bedrock client with correct region
        config = Config(
            retries=dict(max_attempts=3),
            connect_timeout=5,
            read_timeout=30
        )
        
        bedrock = boto3.client(
            'bedrock-runtime',
            region_name='us-west-2',
            config=config
        )
        
        # Prepare request for Claude with image support
        message_content = [
            {
                "type": "text",
                "text": current_prompt
            }
        ]

        # Add image if provided
        if image_data:
            message_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_data
                }
            })

        # Create Claude request
        claude_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": message_content
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        # Call Claude
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps(claude_request)
        )
        
        # Parse response
        response_body = json.loads(response.get('body').read())
        answer = response_body['content'][0]['text']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'prompt': current_prompt,
                'response': answer,
                'model': 'Claude 3.5 Sonnet'
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            }, ensure_ascii=False)
        }