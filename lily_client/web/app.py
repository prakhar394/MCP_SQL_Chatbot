from quart import Quart, render_template, request, jsonify, Response
import asyncio
import sys
import os
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Add the parent directory to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from client import MCPClient

app = Quart(__name__)

# Disable caching for static files in development
@app.after_request
async def after_request(response):
    if app.debug:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

client = None

@app.before_serving
async def startup():
    global client
    if client is None:
        client = MCPClient()
        # Connect to required servers
        try:
            await client.connect_to_server("rag", "../../mcp_servers/rag/rag_server.py")
            await client.connect_to_server("mysql", "../../mcp_servers/mysql/mysql_server.py")
            logger.info("Successfully connected to required servers")
        except Exception as e:
            logger.error(f"Failed to connect to servers: {str(e)}")

@app.after_serving
async def shutdown():
    global client
    if client is not None:
        try:
            await client.cleanup()
        except Exception as e:
            # Suppress cleanup errors during shutdown - they're often harmless
            logger.warning(f"Error during cleanup (this is usually safe to ignore): {str(e)}")
        finally:
            client = None

@app.route('/')
async def index():
    return await render_template('index.html')

@app.route('/api/chat', methods=['POST'])
async def chat():
    global client
    if client is None:
        return jsonify({'error': 'No MCP client initialized'}), 400
    
    data = await request.get_json()
    query = data.get('query')
    
    if not query:
        return jsonify({'error': 'Missing query'}), 400
    
    async def generate():
        try:
            # Set a timeout for the entire query processing
            async with asyncio.timeout(120):  # 2 minute timeout for the entire process
                response = await client.process_query(query)
                yield f"data: {json.dumps({'response': response})}\n\n"
        except asyncio.TimeoutError:
            error_msg = "The request took too long to process. Please try again with a simpler query."
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            logger.error("Timeout processing query")
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            logger.error(f"Error in chat endpoint: {str(e)}")
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/reset', methods=['POST'])
async def reset_chat():
    global client
    if client is None:
        return jsonify({'error': 'No MCP client initialized'}), 400
    
    try:
        intro_message = await client.reset_chat()
        return jsonify({
            'message': 'Chat history has been reset',
            'introduction': intro_message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/regenerate', methods=['POST'])
async def regenerate():
    global client
    if client is None:
        return jsonify({'error': 'No MCP client initialized'}), 400
    
    data = await request.get_json()
    query = data.get('query')
    
    if not query:
        return jsonify({'error': 'Missing query'}), 400
    
    async def generate():
        try:
            # Set a timeout for the entire query processing
            async with asyncio.timeout(120):  # 2 minute timeout for the entire process
                response = await client.regenerate_response(query)
                yield f"data: {json.dumps({'response': response})}\n\n"
        except asyncio.TimeoutError:
            error_msg = "The request took too long to process. Please try again with a simpler query."
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            logger.error("Timeout processing query")
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            logger.error(f"Error in regenerate endpoint: {str(e)}")
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    import signal
    import sys
    
    def signal_handler(sig, frame):
        """Handle shutdown signals gracefully"""
        logger.info("Shutting down...")
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        app.run(debug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running app: {str(e)}")
        raise 