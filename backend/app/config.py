import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 9000
    DEMO_APP_PORT: int = 9090
    ENVIRONMENT: str = "development"

    EC2_HOST_NAME: str = "ec2-botify-demo-node"
    EC2_HOST_IP: str = "127.0.0.1"

    SPLUNK_HEC_URL: str = "http://localhost:8088/services/collector/event"
    SPLUNK_HEC_TOKEN: str = "demo-splunk-hec-token"
    SPLUNK_INDEX: str = "main" # Updated directly to 'main' for Botify integration
    SPLUNK_LOG_FILE_PATH: str = "./data/logs/splunk_events.log"
    SPLUNK_CSV_FILE_PATH: str = "./data/logs/splunk_events.csv"
    SPLUNK_ENABLED: bool = True

    DYNATRACE_TENANT_URL: str = "http://localhost:9999"
    DYNATRACE_API_TOKEN: str = "demo-dt-token"
    DYNATRACE_ENABLED: bool = True

    MAX_SCENARIO_DURATION_SECONDS: int = 300
    MAX_CPU_LOAD_PERCENT: int = 75
    MAX_MEMORY_ALLOCATION_MB: int = 1024
    MAX_REQUESTS_PER_SECOND: int = 200

    DATABASE_URL: str = "sqlite:///./data/history.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
