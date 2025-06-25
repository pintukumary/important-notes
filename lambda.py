import boto3
import json
from boto3.dynamodb.conditions import Key, Attr
import time
from botocore.exceptions import ClientError

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table_name = 'UserProfiles'

def create_table_if_not_exists():
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
                {'AttributeName': 'last_updated', 'KeyType': 'RANGE'}  # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'last_updated', 'AttributeType': 'N'},
                {'AttributeName': 'email', 'AttributeType': 'S'}  # For GSI
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [
                        {'AttributeName': 'email', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        # Wait for the table to be created
        table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
        return "Table created successfully"
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            return "Table already exists"
        else:
            raise e

def insert_user_profile(user_data):
    table = dynamodb.Table(table_name)
    response = table.put_item(Item=user_data)
    return "User profile added successfully"

def query_by_user_id(user_id):
    table = dynamodb.Table(table_name)
    response = table.query(
        KeyConditionExpression=Key('user_id').eq(user_id)
    )
    return response['Items']

def query_by_email(email):
    table = dynamodb.Table(table_name)
    response = table.query(
        IndexName='EmailIndex',
        KeyConditionExpression=Key('email').eq(email)
    )
    return response['Items']

def update_user_profile(key, update_data):
    table = dynamodb.Table(table_name)
    
    # Build update expression and expression attribute values
    update_expression = "SET "
    expression_values = {}
    
    for k, v in update_data.items():
        if k not in ['user_id', 'last_updated']:  # Skip primary key attributes
            update_expression += f"{k} = :{k.replace('.', '_')}, "
            expression_values[f":{k.replace('.', '_')}"] = v
    
    # Remove trailing comma and space
    update_expression = update_expression[:-2]
    
    response = table.update_item(
        Key=key,
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
        ReturnValues="UPDATED_NEW"
    )
    return response['Attributes']

def lambda_handler(event, context):
    operation = event.get('operation')
    result = {}
    
    try:
        if operation == 'create_table':
            result = create_table_if_not_exists()
        
        elif operation == 'insert_user':
            user_data = event.get('user_data')
            if not user_data:
                return {
                    'statusCode': 400,
                    'body': 'Missing user_data in request'
                }
            result = insert_user_profile(user_data)
        
        elif operation == 'query_by_user_id':
            user_id = event.get('user_id')
            if not user_id:
                return {
                    'statusCode': 400,
                    'body': 'Missing user_id in request'
                }
            result = query_by_user_id(user_id)
        
        elif operation == 'query_by_email':
            email = event.get('email')
            if not email:
                return {
                    'statusCode': 400,
                    'body': 'Missing email in request'
                }
            result = query_by_email(email)
        
        elif operation == 'update_user':
            key = event.get('key')
            update_data = event.get('update_data')
            if not key or not update_data:
                return {
                    'statusCode': 400,
                    'body': 'Missing key or update_data in request'
                }
            result = update_user_profile(key, update_data)
        
        else:
            return {
                'statusCode': 400,
                'body': f'Unsupported operation: {operation}'
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }
