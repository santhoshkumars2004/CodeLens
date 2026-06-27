#!/bin/bash
# CodeLens — AWS Deployment Helper
set -e

echo "🚀 CodeLens AWS Deployment"
echo "================================"

# Verify AWS CLI
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI required"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl required"; exit 1; }

CLUSTER_NAME="${CLUSTER_NAME:-codelens-cluster}"
REGION="${AWS_REGION:-us-east-1}"

echo "Cluster: $CLUSTER_NAME"
echo "Region: $REGION"

# Update kubeconfig
echo ""
echo "📋 Updating kubeconfig..."
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION"

# Apply manifests
echo ""
echo "🔧 Applying Kubernetes manifests..."
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/backend/
kubectl apply -f kubernetes/frontend/
kubectl apply -f kubernetes/chromadb/
kubectl apply -f kubernetes/monitoring/
kubectl apply -f kubernetes/ingress/

# Wait for rollout
echo ""
echo "⏳ Waiting for deployments..."
kubectl rollout status deployment/backend -n codelens --timeout=300s
kubectl rollout status deployment/frontend -n codelens --timeout=300s

# Show status
echo ""
echo "✅ Deployment complete!"
kubectl get all -n codelens
