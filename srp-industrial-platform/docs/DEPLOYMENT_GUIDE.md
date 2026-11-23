# Deployment

Run `docker compose up --build -d` in the project directory. Override published ports through a local .env file using .env.example. Frontends proxy API and SSE through the same origin. The initialization container generates distinct MQTT credentials and a PostgreSQL password into isolated volumes. The broker and interfaces bind their published ports to loopback.

Use `docker compose ps` and `docker compose logs mqtt simulator apm ml-worker` to inspect startup. Register each equipment configuration in both apps before starting a new simulation run. Presets are provisioned by both apps. For live field inputs, configure a publisher authorized for the same topic and supply its corresponding equipment data to APM.

Prepare host-side verification with `python -m pip install -r requirements.txt` and `python -m playwright install chromium`. Run `python scripts/run_acceptance.py` to verify the existing stack or add `--start-compose` to start it. To verify without Docker, install npm dependencies and run `python scripts/run_acceptance.py --local` with any required port overrides.

For an explicitly reviewed experimental RF artifact, set SRP_MODEL_PATH=/models/model.joblib in .env before starting the worker. For CNN inference in Compose, set SRP_ENABLE_CNN=1 and SRP_MODEL_PATH=/models/cnn.pt. For native CNN inference, install CPU PyTorch and set SRP_MODEL_PATH to the .pt file. Default inference uses the rule baseline. Accept artifact files from a trusted training environment.
