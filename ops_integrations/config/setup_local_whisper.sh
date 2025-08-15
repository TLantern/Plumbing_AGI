#!/bin/bash

# Setup script for local Whisper v3 installation
# This script installs the required dependencies for self-hosted Whisper transcription

echo "🔧 Setting up Local Whisper v3 for Plumbing Ops..."

# Check if CUDA is available
if command -v nvidia-smi &> /dev/null; then
    echo "✅ CUDA detected, installing PyTorch with CUDA support..."
    CUDA_VERSION=$(nvidia-smi --query-gpu=cuda_version --format=csv,noheader,nounits | head -1)
    echo "Detected CUDA version: $CUDA_VERSION"
    
    # Install PyTorch with appropriate CUDA version
    if [[ "$CUDA_VERSION" == "12"* ]]; then
        echo "Installing PyTorch with CUDA 12.x support..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    elif [[ "$CUDA_VERSION" == "11"* ]]; then
        echo "Installing PyTorch with CUDA 11.x support..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
        echo "⚠️  Unknown CUDA version, installing CPU version..."
        pip install torch torchvision torchaudio
    fi
else
    echo "⚠️  CUDA not detected, installing CPU-only PyTorch..."
    pip install torch torchvision torchaudio
fi

# Install OpenAI Whisper from GitHub (for v3 support)
echo "📦 Installing OpenAI Whisper from GitHub..."
pip install git+https://github.com/openai/whisper.git

# Install additional dependencies
echo "📦 Installing audio processing dependencies..."
pip install numpy>=1.21.0 scipy>=1.7.0

# Optional: Install performance optimizations
echo "📦 Installing optional performance optimizations..."
pip install transformers>=4.20.0 accelerate>=0.20.0

echo "✅ Local Whisper v3 setup complete!"
echo ""
echo "To test the installation, run:"
echo "python -c \"import whisper; print('Whisper version:', whisper.__version__)\""
echo ""
echo "To download the large-v3 model (first time will be slow):"
echo "python -c \"import whisper; whisper.load_model('large-v3')\""
echo ""
echo "Configuration:"
echo "- Set USE_LOCAL_WHISPER = True in phone.py"
echo "- Set LOCAL_WHISPER_MODEL = 'large-v3' for best quality"
echo "- The system will automatically fall back to OpenAI Whisper if local fails" 