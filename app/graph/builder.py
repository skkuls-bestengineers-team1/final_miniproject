'''그래프 조립.

담당: 나송주

START → supervisor → worker 또는 fallback
worker → validator → respond | 같은 worker | fallback
respond, fallback → END
'''

from langgraph.graph import END, START, StateGraph

from app.graph.fallback import fallback
from app.graph.state import State
from app.graph.supervisor import route_from_supervisor, supervisor
from app.graph.validator import respond, route_from_validator, validator
from app.workers.worker1_store import worker1
from app.workers.worker2_stock import worker2
from app.workers.worker3_delivery import worker3
from app.workers.worker4_order import worker4


def build_graph(
        checkpointer
):
    builder = StateGraph(State)

    builder.add_node('supervisor', supervisor)
    builder.add_node('worker1', worker1)
    builder.add_node('worker2', worker2)
    builder.add_node('worker3', worker3)
    builder.add_node('worker4', worker4)
    builder.add_node('validator', validator)
    builder.add_node('respond', respond)
    builder.add_node('fallback', fallback)

    builder.add_edge(START, 'supervisor')

    builder.add_conditional_edges(
        'supervisor',
        route_from_supervisor,
        ['worker1', 'worker2', 'worker3', 'worker4', 'fallback'],
    )

    for name in ('worker1', 'worker2', 'worker3', 'worker4'):
        builder.add_edge(name, 'validator')

    builder.add_conditional_edges(
        'validator',
        route_from_validator,
        ['respond', 'worker1', 'worker2', 'worker3', 'worker4', 'fallback'],
    )

    builder.add_edge('respond', END)
    builder.add_edge('fallback', END)

    return builder.compile(checkpointer=checkpointer)
