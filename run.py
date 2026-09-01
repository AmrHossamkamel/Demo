import os
import sys
import argparse
import uvicorn
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("botify_launcher")

def main():
    parser = argparse.ArgumentParser(description="Botify Observability Demo Testing Platform")
    parser.add_argument("--port", type=int, help="Custom server port (default: 9000)")
    parser.add_argument("--host", type=str, help="Custom server host (default: 0.0.0.0)")
    args = parser.parse_args()

    from backend.app.config import settings

    port = args.port or int(os.getenv("PORT", settings.PORT))
    host = args.host or os.getenv("HOST", settings.HOST)

    logger.info("================================================================")
    logger.info("  STARTING BOTIFY OBSERVABILITY DEMO TESTING PLATFORM         ")
    logger.info("================================================================")

    os.makedirs("./data/logs", exist_ok=True)

    logger.info(f"Target EC2 Host Name : {settings.EC2_HOST_NAME}")
    logger.info(f"Splunk Log File      : {settings.SPLUNK_LOG_FILE_PATH}")
    logger.info(f"Demo Platform API    : http://{host}:{port}")
    logger.info(f"Demo Banking Target  : http://{host}:{port}/demo-target")

    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
