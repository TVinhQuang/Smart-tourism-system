from routing import app as routing_app
from server import app as server_app
if __name__ == '__main__':
    routing_app.run(debug=True, port=5000)
