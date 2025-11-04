ECR_IMAGE_TAG=web-v0.0.1-dev

aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin 196441063343.dkr.ecr.ap-northeast-2.amazonaws.com
# 1. 단일 플랫폼 (예: amd64)로 빌드하고 로컬에 로드
docker buildx build --platform linux/amd64 -f Dockerfile.web -t sb-fsts:$ECR_IMAGE_TAG --load .

# 2. 로컬에 로드된 이미지를 ECR 레포지토리로 태그 변경
docker tag sb-fsts:$ECR_IMAGE_TAG 196441063343.dkr.ecr.ap-northeast-2.amazonaws.com/sb-fsts-ecr:$ECR_IMAGE_TAG

# 3. ECR에 푸시
docker push 196441063343.dkr.ecr.ap-northeast-2.amazonaws.com/sb-fsts-ecr:$ECR_IMAGE_TAG

# ECS 서비스 업데이트
# aws ecs update-service \
#     --cluster $CLUSTER_NAME \
#     --service $SERVICE_NAME \
#     --force-new-deployment