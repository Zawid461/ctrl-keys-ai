import threading


generation_result = None
generation_running = False


def run_graph(graph, payload):

    global generation_result
    global generation_running

    generation_running = True

    try:
        generation_result = graph.invoke(payload)

    finally:
        generation_running = False