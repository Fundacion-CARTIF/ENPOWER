import plotly.graph_objects as go

# Define the nodes and their positions
nodes = [
    {"name": "Socio-Demographic Factors", "x": 0.2, "y": 0.8},
    {"name": "Psychological Factors", "x": 0.8, "y": 0.8},
    {"name": "Building Systems", "x": 0.5, "y": 0.2},
    {"name": "Household Size", "x": 0.1, "y": 0.9},
    {"name": "Income", "x": 0.3, "y": 0.9},
    {"name": "Dwelling Type", "x": 0.2, "y": 0.7},
    {"name": "Employment Status", "x": 0.1, "y": 0.7},
    {"name": "Knowledge", "x": 0.7, "y": 0.9},
    {"name": "Norms", "x": 0.9, "y": 0.9},
    {"name": "Values & Beliefs", "x": 0.8, "y": 0.7},
    {"name": "Perceived Control", "x": 0.9, "y": 0.7},
    {"name": "Windows", "x": 0.4, "y": 0.1},
    {"name": "Thermostats", "x": 0.6, "y": 0.1},
    {"name": "Lights", "x": 0.5, "y": 0.3},
    {"name": "Equipment", "x": 0.6, "y": 0.3}
]

# Define the links between nodes
links = [
    {"source": "Socio-Demographic Factors", "target": "Household Size"},
    {"source": "Socio-Demographic Factors", "target": "Income"},
    {"source": "Socio-Demographic Factors", "target": "Dwelling Type"},
    {"source": "Socio-Demographic Factors", "target": "Employment Status"},
    {"source": "Psychological Factors", "target": "Knowledge"},
    {"source": "Psychological Factors", "target": "Norms"},
    {"source": "Psychological Factors", "target": "Values & Beliefs"},
    {"source": "Psychological Factors", "target": "Perceived Control"},
    {"source": "Building Systems", "target": "Windows"},
    {"source": "Building Systems", "target": "Thermostats"},
    {"source": "Building Systems", "target": "Lights"},
    {"source": "Building Systems", "target": "Equipment"},
    {"source": "Socio-Demographic Factors", "target": "Building Systems"},
    {"source": "Psychological Factors", "target": "Building Systems"},
    {"source": "Socio-Demographic Factors", "target": "Psychological Factors"}
]

# Create node trace
node_trace = go.Scatter(
    x=[node["x"] for node in nodes],
    y=[node["y"] for node in nodes],
    text=[node["name"] for node in nodes],
    mode='markers+text',
    textposition="bottom center",
    marker=dict(size=15, color="skyblue"),
    hoverinfo="text"
)

# Create edge trace
edge_x = []
edge_y = []
for link in links:
    source_node = next(node for node in nodes if node["name"] == link["source"])
    target_node = next(node for node in nodes if node["name"] == link["target"])
    edge_x.extend([source_node["x"], target_node["x"], None])
    edge_y.extend([source_node["y"], target_node["y"], None])

edge_trace = go.Scatter(
    x=edge_x,
    y=edge_y,
    line=dict(width=1, color="gray"),
    hoverinfo="none",
    mode="lines"
)

# Combine traces into a figure
fig = go.Figure(data=[edge_trace, node_trace])

# Set layout
fig.update_layout(
    title="Relationships Between Factors Influencing Energy Consumption",
    title_x=0.5,
    showlegend=False,
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=False, zeroline=False),
    margin=dict(l=40, r=40, t=40, b=40)
)

# Display the figure
fig.show()








import matplotlib.pyplot as plt
import networkx as nx

# Create a directed graph
G = nx.DiGraph()

# Define nodes and their categories
categories = {
    "Socio-Demographic Factors": ["Household Size", "Income", "Dwelling Type", "Employment Status"],
    "Psychological Factors": ["Knowledge", "Norms", "Values & Beliefs", "Perceived Control"],
    "Building Systems": ["Windows", "Thermostats", "Lights", "Equipment"]
}

# Add nodes to the graph
for category, nodes in categories.items():
    G.add_node(category, type="category")
    for node in nodes:
        G.add_node(node, type="factor")
        G.add_edge(category, node)

# Define relationships between major categories
G.add_edge("Socio-Demographic Factors", "Building Systems", relationship="Direct Interaction")
G.add_edge("Psychological Factors", "Building Systems", relationship="Behavioral Influence")
G.add_edge("Socio-Demographic Factors", "Psychological Factors", relationship="Moderating Effect")

# Draw the graph
pos = nx.spring_layout(G, seed=42)  # Layout for consistent positioning
plt.figure(figsize=(12, 8))

# Draw nodes and edges
nx.draw_networkx_nodes(G, pos, node_color="skyblue", node_size=2000)
nx.draw_networkx_edges(G, pos, edge_color="gray", arrows=True)
nx.draw_networkx_labels(G, pos, font_size=10, font_color="black")

# Add edge labels
edge_labels = nx.get_edge_attributes(G, "relationship")
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="red")

# Add title and display
plt.title("Relationships Between Factors Influencing Energy Consumption")
plt.axis("off")
plt.show()
