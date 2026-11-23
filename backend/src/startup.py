import logging
import os

import uvicorn

from .storage import initialize

if __name__ == '__main__':
    initialize()
    if os.getenv('SEED_DEMO', 'true').lower() == 'true':
        try:
            from scripts.seed_demo import seed
            logging.warning('Demo seed: %s', seed())
        except Exception:
            logging.exception('Demo seed failed')
    uvicorn.run('src.app:app', host='0.0.0.0', port=8000)
