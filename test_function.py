import azure.functions as func
import logging

app = func.FunctionApp()

@app.route(route="test")
def test(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Test function called')
    return func.HttpResponse("It works!", status_code=200)
