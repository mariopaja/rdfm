import inspect
import urllib
import pytest
import werkzeug.routing
from rdfm_mgmt_server import app
from urllib.parse import unquote


# These endpoints should be excluded from all tests below
ENDPOINT_EXCLUDE_GLOBAL = [
    "static", # Flask default route
    "rdfm-server-api-v1.rdfm-server-packages.fetch_local_package",
    "rdfm-server-api-v1.rdfm-server-updates.check_for_update",
]


def get_view_funcs():
    url_map: werkzeug.routing.Map = app.url_map
    rule: werkzeug.routing.Rule

    view_functions = []
    for rule in url_map.iter_rules():
        endpoint = rule.endpoint
        if endpoint in ENDPOINT_EXCLUDE_GLOBAL:
            print("Skipping route:", endpoint)
            continue

        # Extract the view function for the route
        func = app.view_functions[endpoint]
        print(endpoint, func, vars(func))

        view_functions.append((endpoint, func))
    return view_functions


@pytest.mark.parametrize(['endpoint', 'func'],
                         get_view_funcs())
def test_authorization_on_all_routes(endpoint, func):
    """ This verifies that all routes have some authorization checks.

    All routes must be marked using the corresponding management/device API
    decorator which protect access to the resources using the proper auth methods.
    """
    # Check for the presence of a decorator
    # The device/management API decorators add a special field for identification
    error_string = (f"route function {func.__name__} should be decorated using "
                    "a management, device or public API decorator, but none was found")
    assert hasattr(func, "__rdfm_api_privileges__"), error_string


@pytest.mark.parametrize(['endpoint', 'func'],
                         get_view_funcs())
def test_docstrings_on_all_routes(endpoint, func):
    """ This verifies that all routes have a defined docstring.
    """
    if endpoint.startswith('rdfm-server-api-v1.rdfm-server-devices.'):
        pytest.skip("device API routes will be subject to a refactor")

    error_string = (f"route function {func.__name__} should have a docstring")
    assert hasattr(func, "__doc__"), error_string
    assert func.__doc__ is not None, error_string
