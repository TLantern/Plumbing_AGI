# Local Whisper v3 Setup Guide

This guide will help you set up self-hosted Whisper v3 for high-quality transcription in your plumbing phone system.

## 🚀 Quick Setup

### 1. Install Dependencies

Run the automated setup script:

```bash
cd ops_integrations
./setup_local_whisper.sh
```

### 2. Test Installation

Verify everything is working:

```bash
python test_local_whisper.py
```

### 3. Enable Local Whisper

In `phone.py`, ensure these settings are enabled:

```python
USE_LOCAL_WHISPER = True
LOCAL_WHISPER_MODEL = "large-v3"  # Best quality
LOCAL_WHISPER_DEVICE = None  # Auto-detect
```

## 📋 System Requirements

### Minimum Requirements
- **RAM**: 8GB (16GB recommended)
- **Storage**: 10GB free space for models
- **Python**: 3.8+

### GPU Requirements (Optional but Recommended)
- **CUDA**: 11.8 or 12.x
- **GPU Memory**: 8GB+ for large-v3 model
- **GPU**: NVIDIA GPU with CUDA support

### CPU-Only Setup
- **CPU**: 4+ cores recommended
- **RAM**: 16GB+ recommended
- **Performance**: ~10-30 seconds per transcription

## 🔧 Manual Installation

If the automated script doesn't work, install manually:

### 1. Install PyTorch

**For CUDA 12.x:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**For CUDA 11.8:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**For CPU only:**
```bash
pip install torch torchvision torchaudio
```

### 2. Install Whisper

```bash
pip install git+https://github.com/openai/whisper.git
```

### 3. Install Additional Dependencies

```bash
pip install numpy>=1.21.0 scipy>=1.7.0
pip install transformers>=4.20.0 accelerate>=0.20.0
```

## 🎯 Model Options

### Available Models

| Model | Size | Speed | Quality | RAM Usage | GPU Memory |
|-------|------|-------|---------|-----------|------------|
| `tiny` | 39MB | Fastest | Basic | 1GB | 1GB |
| `base` | 74MB | Fast | Good | 1GB | 1GB |
| `small` | 244MB | Medium | Better | 2GB | 2GB |
| `medium` | 769MB | Slow | Good | 5GB | 5GB |
| `large-v2` | 1550MB | Slower | Excellent | 10GB | 10GB |
| `large-v3` | 1550MB | Slowest | Best | 10GB | 10GB |

### Recommended Settings

**For Production (Best Quality):**
```python
LOCAL_WHISPER_MODEL = "large-v3"
```

**For Development (Fast Testing):**
```python
LOCAL_WHISPER_MODEL = "base"
```

**For Balanced Performance:**
```python
LOCAL_WHISPER_MODEL = "medium"
```

## ⚙️ Configuration Options

### Device Selection

```python
# Auto-detect (recommended)
LOCAL_WHISPER_DEVICE = None

# Force CPU
LOCAL_WHISPER_DEVICE = "cpu"

# Force GPU
LOCAL_WHISPER_DEVICE = "cuda"
```

### Performance Tuning

```python
# In local_whisper.py, you can adjust:
fp16 = True  # Use half-precision (faster, less memory)
verbose = False  # Reduce logging
```

## 🔍 Troubleshooting

### Common Issues

**1. CUDA Out of Memory**
```
RuntimeError: CUDA out of memory
```
**Solution:** Use a smaller model or reduce batch size.

**2. Model Download Fails**
```
Error downloading model
```
**Solution:** Check internet connection and disk space.

**3. Import Errors**
```
ModuleNotFoundError: No module named 'whisper'
```
**Solution:** Reinstall Whisper: `pip install git+https://github.com/openai/whisper.git`

**4. Slow Performance**
**Solution:** 
- Use GPU if available
- Use smaller model for testing
- Enable fp16 precision

### Performance Optimization

**For GPU Users:**
```python
# Enable mixed precision
fp16 = True
```

**For CPU Users:**
```python
# Use smaller models
LOCAL_WHISPER_MODEL = "base"  # or "small"
```

## 📊 Performance Benchmarks

### Transcription Speed (seconds per minute of audio)

| Model | CPU (4 cores) | GPU (RTX 3080) | GPU (RTX 4090) |
|-------|---------------|----------------|----------------|
| tiny | 15-20 | 2-3 | 1-2 |
| base | 25-30 | 3-4 | 2-3 |
| small | 40-50 | 5-6 | 3-4 |
| medium | 60-80 | 8-10 | 5-6 |
| large-v2 | 90-120 | 12-15 | 8-10 |
| large-v3 | 100-140 | 15-20 | 10-12 |

### Memory Usage

| Model | CPU RAM | GPU Memory |
|-------|---------|------------|
| tiny | 1GB | 1GB |
| base | 1GB | 1GB |
| small | 2GB | 2GB |
| medium | 5GB | 5GB |
| large-v2 | 10GB | 10GB |
| large-v3 | 10GB | 10GB |

## 🔄 Fallback Configuration

The system automatically falls back to OpenAI Whisper API if local Whisper fails:

```python
# In phone.py
USE_LOCAL_WHISPER = True  # Try local first
# Falls back to OpenAI if local fails
```

## 📝 Testing

### Run Full Test Suite
```bash
python test_local_whisper.py
```

### Test Specific Components
```python
# Test imports
python -c "import whisper; print('Whisper version:', whisper.__version__)"

# Test model loading
python -c "import whisper; whisper.load_model('base')"

# Test transcription
python -c "import whisper; m = whisper.load_model('base'); print('Model loaded successfully')"
```

## 🎉 Success Indicators

When everything is working correctly, you should see:

1. **Setup script completes without errors**
2. **Test script shows all tests passed**
3. **Phone system logs show "Using local Whisper large-v3"**
4. **Transcription quality is noticeably better**
5. **No API costs for transcription**

## 📞 Integration with Phone System

The local Whisper integration is seamless:

- **Automatic fallback** to OpenAI if local fails
- **Same API interface** as OpenAI Whisper
- **Better quality** with large-v3 model
- **No API costs** for transcription
- **Faster response** times (no network latency)

## 🔧 Advanced Configuration

### Custom Model Path
```python
# Set custom model cache directory
import os
os.environ["WHISPER_MODEL_DIR"] = "/path/to/models"
```

### Batch Processing
```python
# For processing multiple files efficiently
adapter = LocalWhisperAdapter("large-v3")
# Reuse the same model instance for multiple transcriptions
```

### Memory Optimization
```python
# Clear GPU cache between transcriptions
import torch
torch.cuda.empty_cache()
```

---

**Need help?** Check the troubleshooting section or run the test script to diagnose issues. 