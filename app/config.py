from dotenv import load_dotenv

import os

load_dotenv()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
LLAMA_API_KEY = os.getenv('LLAMA_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')