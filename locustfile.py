from locust import HttpUser, task, between
import os


TARGET_PATH = os.getenv("TARGET_PATH", "/")
WAIT_MIN = float(os.getenv("WAIT_MIN", "0.2"))
WAIT_MAX = float(os.getenv("WAIT_MAX", "1.0"))


class MyUser(HttpUser):
    wait_time = between(WAIT_MIN, WAIT_MAX)

    @task
    def target_path(self):
        self.client.get(TARGET_PATH)