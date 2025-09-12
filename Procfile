web: python3 -m ops_integrations.services.salon_phone_service
release: python3 -c "import asyncio; from ops_integrations.services.init_db import initialize_salon_database; asyncio.run(initialize_salon_database())"
