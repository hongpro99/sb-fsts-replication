import boto3

ecs = boto3.client('ecs', region_name='ap-northeast-2')

image_uri = '196441063343.dkr.ecr.ap-northeast-2.amazonaws.com/sb-fsts-ecr:ecs-task-v0.0.1'

response = ecs.register_task_definition(
    family='sb-fsts-td',  # task 정의 이름
    requiresCompatibilities=['FARGATE'],
    networkMode='awsvpc',
    cpu='2048',  # 1 vCPU
    memory='4096',  # 2 GB
    executionRoleArn='arn:aws:iam::196441063343:role/sb-common-role',
    taskRoleArn='arn:aws:iam::196441063343:role/sb-common-role',
    containerDefinitions=[
        {
            'name': 'fsts-ecs-container',
            'image': image_uri,  # 새로 빌드한 ECR 이미지 URL
            'essential': True,
            'environment': [
                {'name': 'EXAMPLE', 'value': 'yes'}
            ],
            'logConfiguration': {
                'logDriver': 'awslogs',
                'options': {
                    'awslogs-group': '/ecs/sb-fsts-td',
                    'awslogs-region': 'ap-northeast-2',
                    'awslogs-stream-prefix': 'ecs'
                }
            }
        }
    ]
)

print(response['taskDefinition']['taskDefinitionArn'])