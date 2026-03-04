class TestContext:
    """
    Helper class to handle callbacks for logging and progress updates.
    Allows logic to be used with or without GUI.
    """
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.should_stop = False

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[LOG] {message}")

    def report_progress(self, value):
        if self.progress_callback:
            self.progress_callback(value)

    def check_stop(self):
        return self.should_stop

    def request_stop(self):
        self.should_stop = True
