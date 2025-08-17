import http.server
import socketserver
import json
import time

PORT = 11434
HANDLER = http.server.SimpleHTTPRequestHandler

class OllamaMockHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/generate':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            
            print(f"Mock Server: Received request for model '{request_body.get('model')}'")
            print(f"Mock Server: Prompt received: '{request_body.get('prompt')[:100]}...'")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Simulate Ollama's streaming response
            response_content = "This is a mock AI summary from the test server."
            for char in response_content:
                response_chunk = {
                    "model": request_body.get('model'),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
                    "response": char,
                    "done": False
                }
                self.wfile.write(json.dumps(response_chunk).encode('utf-8'))
                self.wfile.write(b'\n')
                time.sleep(0.01) # Simulate token streaming
            
            # Final chunk
            final_chunk = {
                "done": True
            }
            self.wfile.write(json.dumps(final_chunk).encode('utf-8'))
            self.wfile.write(b'\n')
            print("Mock Server: Sent mock summary response.")
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(("", PORT), OllamaMockHandler) as httpd:
    print(f"Mock Ollama server listening on port {PORT}")
    httpd.serve_forever()
