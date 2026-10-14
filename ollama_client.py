import logging
import time
from ollama import Client, ResponseError


class ProjectClient(Client):
    def chat(self, *args, **kwargs):
        kwargs.setdefault("think", False)
        for attempt in range(3):
            try:
                return super().chat(*args, **kwargs)
            except ResponseError as error:
                if error.status_code not in (429, 503) or attempt == 2:
                    raise
                logging.warning("Ollama status=%s; retry %s/2", error.status_code, attempt + 1)
                time.sleep(3)
