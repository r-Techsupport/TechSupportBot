from . import ConfigSchema

class Config(ConfigSchema):
    def load_json():
        ...
    ...

config = Config()

config.reports_channel.send(content="example")
