from model_registry.registry import Registry
from shared.http_api import serve


def main():
    registry = Registry()

    def dispatch(method, route, query, body):
        if route==["registry"]:
            return registry.metadata()
        if method=="POST" and route==["predict"]:
            return registry.predict(body)
        raise KeyError()

    serve(8003,dispatch)


if __name__=="__main__":
    main()
