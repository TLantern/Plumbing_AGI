from setuptools import setup, find_packages

setup(
    name="plumbing-agi",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0",
        "pydantic-settings>=2.0",
        "httpx>=0.24",
        "requests>=2.31",
        "python-dotenv>=1.0",
        "celery>=5.0",
        "google-auth>=2.0",
        "google-auth-oauthlib>=1.0",
        "google-auth-httplib2>=0.1",
        "google-api-python-client>=2.0",
        "requests-oauthlib>=1.3.0",
        "twilio==8.10.0",
        "clicksend-client>=5.0.0",
        "openai>=1.0",
        "Flask==2.3.3",
        "fastapi>=0.100",
        "uvicorn>=0.20",
        "websockets>=11.0",
    ],
    python_requires=">=3.8",
) 