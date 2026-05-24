import ast
from pathlib import Path
import networkx as nx
from pyvis.network import Network


def get_gitignore_patterns(repo_path):
    """Parse .gitignore and return a list of patterns to exclude."""
    gitignore = Path(repo_path) / ".gitignore"
    patterns = []
    if gitignore.exists():
        with open(gitignore, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line.rstrip("/"))
    return patterns


def is_ignored(filepath, repo_path, patterns):
    """Check if a file matches any gitignore pattern."""
    relative = Path(filepath).relative_to(repo_path)
    parts = relative.parts
    for pattern in patterns:
        if pattern in parts:
            return True
        if relative.match(pattern):
            return True
    return False


def get_internal_packages(repo_path, always_exclude):
    """
    Auto-detect internal package names supporting both layouts:
    - Standard: /mypackage/__init__.py
    - Src layout: /src/mypackage/__init__.py
    """
    repo = Path(repo_path)
    packages = set()

    # Standard layout: top-level directories with __init__.py
    for item in repo.iterdir():
        if (
            item.is_dir()
            and item.name not in always_exclude
            and not item.name.startswith(".")
            and (item / "__init__.py").exists()
        ):
            packages.add(item.name)

    # Src layout: look one level deeper inside src/
    src_dir = repo / "src"
    if src_dir.exists():
        for item in src_dir.iterdir():
            if (
                item.is_dir()
                and item.name not in always_exclude
                and not item.name.startswith(".")
                and (item / "__init__.py").exists()
            ):
                packages.add(item.name)

    # Fallback: use repo directory name
    if not packages:
        packages.add(repo.name)

    return packages


def get_imports(filepath):
    """Extract all imports from a Python file using AST."""
    imports = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception:
        pass
    return imports


def build_graph(repo_path):
    """Walk the repo and build a dependency graph."""
    G = nx.DiGraph()
    repo = Path(repo_path)
    patterns = get_gitignore_patterns(repo_path)

    always_exclude = {".git", "__pycache__", ".tox", ".eggs", "dist", "build"}
    internal_packages = get_internal_packages(repo_path, always_exclude)
    print(f"Detected internal packages: {internal_packages}")

    # Detect if repo uses src layout
    src_dir = repo / "src"
    use_src_layout = src_dir.exists() and any(
        (src_dir / pkg).exists() for pkg in internal_packages
    )

    py_files = [
        f for f in repo.rglob("*.py")
        if not is_ignored(f, repo, patterns)
        and not any(part in always_exclude for part in f.parts)
    ]

    print(f"Found {len(py_files)} Python files. Building graph...")

    for filepath in py_files:
        relative = filepath.relative_to(repo)

        # Strip src/ prefix from node ID so it matches import paths
        if use_src_layout and relative.parts[0] == "src":
            node_id = str(Path(*relative.parts[1:]))
        else:
            node_id = str(relative)

        G.add_node(node_id)

    # Second pass: build edges now that all node IDs are registered
    for filepath in py_files:
        relative = filepath.relative_to(repo)

        if use_src_layout and relative.parts[0] == "src":
            node_id = str(Path(*relative.parts[1:]))
        else:
            node_id = str(relative)

        imports = get_imports(filepath)
        for imp in imports:
            if not any(imp == pkg or imp.startswith(pkg + ".") for pkg in internal_packages):
                continue

            imp_path = imp.replace(".", "/") + ".py"

            # If imp_path doesn't exist as a node, try it as a package __init__.py
            # e.g. "flask.py" → "flask/__init__.py"
            if not G.has_node(imp_path):
                init_path = imp.replace(".", "/") + "/__init__.py"
                if G.has_node(init_path):
                    imp_path = init_path
                else:
                    continue

            if node_id != imp_path:
                G.add_edge(node_id, imp_path)

    return G


def render_graph(G, output="blastmap.html"):
    """Render the graph as an interactive HTML file."""
    net = Network(
        height="100vh",
        width="100%",
        directed=True,
        bgcolor="#0f0f0f",
        font_color=True
    )

    # Filter to only nodes with at least 1 connection
    connected = {n for n, d in G.degree() if d > 0}
    subgraph = G.subgraph(connected)

    in_degree = dict(subgraph.in_degree())

    for node in subgraph.nodes():
        size = 10 + (in_degree.get(node, 0) * 3)
        label = Path(node).name
        net.add_node(
            node,
            label=label,
            size=size,
        )

    for edge in subgraph.edges():
        net.add_edge(edge[0], edge[1], arrows="to", color="#444444")

    net.set_options("""
    {
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -200,
                "springLength": 200,
                "springConstant": 0.05,
                "overlap": 1
            },
            "solver": "forceAtlas2Based",
            "stabilization": {
                "enabled": true,
                "iterations": 1000,
                "updateInterval": 25,
                "fit": true
            }
        },
        "nodes": {
            "scaling": {
                "min": 10,
                "max": 40
            }
        },
        "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
        }
    }
    """)

    net.write_html(output)

    with open(output, "r") as f:
        html = f.read()

    navigation_script = """
    <script>
    network.once("stabilizationIterationsDone", function () {
        network.setOptions({ physics: { enabled: false } });

        function getNodeSize(nodeId) {
            const n = nodes.get(nodeId);
            return (n && n.size) ? n.size : 10;
        }

        function separateNodes() {
            const allNodes = nodes.getIds();
            const positions = network.getPositions(allNodes);
            let moved = true;
            let iterations = 0;
            const maxIterations = 500;

            while (moved && iterations < maxIterations) {
                moved = false;
                iterations++;

                for (let i = 0; i < allNodes.length; i++) {
                    for (let j = i + 1; j < allNodes.length; j++) {
                        const idA = allNodes[i];
                        const idB = allNodes[j];
                        const posA = positions[idA];
                        const posB = positions[idB];

                        const sizeA = getNodeSize(idA);
                        const sizeB = getNodeSize(idB);

                        const minDist = sizeA + sizeB + 100;

                        const dx = posB.x - posA.x;
                        const dy = posB.y - posA.y;
                        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;

                        if (dist < minDist) {
                            const overlap = (minDist - dist) / 2;
                            const nx = (dx / dist) * overlap;
                            const ny = (dy / dist) * overlap;

                            positions[idA].x -= nx;
                            positions[idA].y -= ny;
                            positions[idB].x += nx;
                            positions[idB].y += ny;

                            moved = true;
                        }
                    }
                }
            }

            const updates = allNodes.map(id => ({
                id: id,
                x: positions[id].x,
                y: positions[id].y
            }));
            nodes.update(updates);
            console.log(`Overlap resolved in ${iterations} iterations.`);
        }

        separateNodes();
    });

    // --- Search Bar ---
    const searchWrapper = document.createElement("div");
    searchWrapper.style.cssText = `
        position: fixed;
        top: 16px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1001;
        width: 340px;
    `;

    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = "Search files, modules...";
    searchInput.style.cssText = `
        width: 100%;
        padding: 10px 16px;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 8px;
        color: white;
        font-family: monospace;
        font-size: 13px;
        box-sizing: border-box;
        outline: none;
    `;

    const dropdown = document.createElement("div");
    dropdown.style.cssText = `
        background: #1a1a1a;
        border: 1px solid #444;
        border-top: none;
        border-radius: 0 0 8px 8px;
        max-height: 240px;
        overflow-y: auto;
        display: none;
    `;

    searchWrapper.appendChild(searchInput);
    searchWrapper.appendChild(dropdown);
    document.body.appendChild(searchWrapper);

    searchInput.addEventListener("input", function () {
        const query = this.value.trim().toLowerCase();
        dropdown.innerHTML = "";

        if (!query) {
            dropdown.style.display = "none";
            return;
        }

        const allNodes = nodes.get();
        const matches = allNodes.filter(n =>
            n.id.toLowerCase().includes(query) ||
            n.label.toLowerCase().includes(query)
        ).slice(0, 10);

        if (!matches.length) {
            dropdown.style.display = "none";
            return;
        }

        matches.forEach(n => {
            const item = document.createElement("div");
            item.style.cssText = `
                padding: 9px 16px;
                cursor: pointer;
                border-bottom: 1px solid #2a2a2a;
                transition: background 0.15s;
            `;
            item.innerHTML = `
                <div style="color:white; font-size:13px;">${n.label}</div>
                <div style="color:#555; font-size:11px; margin-top:2px;">${n.id}</div>
            `;
            item.onmouseover = () => item.style.background = "#2a2a2a";
            item.onmouseout = () => item.style.background = "transparent";
            item.onclick = () => {
                searchInput.value = n.label;
                dropdown.style.display = "none";
                navigateTo(n.id);
            };
            dropdown.appendChild(item);
        });

        dropdown.style.display = "block";
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", function (e) {
        if (!searchWrapper.contains(e.target)) {
            dropdown.style.display = "none";
        }
    });

    // Keyboard navigation in dropdown
    searchInput.addEventListener("keydown", function (e) {
        const items = dropdown.querySelectorAll("div");
        const active = dropdown.querySelector(".active");
        let index = Array.from(items).indexOf(active);

        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (active) active.classList.remove("active");
            const next = items[Math.min(index + 1, items.length - 1)];
            if (next) {
                next.classList.add("active");
                next.style.background = "#3a3a3a";
            }
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (active) active.classList.remove("active");
            const prev = items[Math.max(index - 1, 0)];
            if (prev) {
                prev.classList.add("active");
                prev.style.background = "#3a3a3a";
            }
        } else if (e.key === "Enter") {
            if (active) active.click();
            else if (items.length > 0) items[0].click();
        } else if (e.key === "Escape") {
            dropdown.style.display = "none";
            searchInput.blur();
        }
    });

    // --- Side Panel ---
    const panel = document.createElement("div");
    panel.style.cssText = `
        position: fixed;
        top: 0; right: 0;
        width: 320px;
        height: 100vh;
        background: #1a1a1a;
        border-left: 1px solid #333;
        color: white;
        font-family: monospace;
        font-size: 13px;
        overflow-y: auto;
        z-index: 1000;
        padding: 16px;
        box-sizing: border-box;
        display: none;
    `;
    document.body.appendChild(panel);

    function buildSection(title, nodeList, color) {
        if (!nodeList.length) return "";
        return `
            <div style="margin-bottom:16px;">
                <div style="color:${color}; font-weight:bold; margin-bottom:8px; font-size:14px;">
                    ${title} (${nodeList.length})
                </div>
                ${nodeList.map(n => `
                    <div
                        onclick="navigateTo('${n.id}')"
                        style="
                            padding: 8px;
                            margin-bottom: 4px;
                            background: #2a2a2a;
                            border-radius: 4px;
                            cursor: pointer;
                            border-left: 3px solid ${color};
                            word-break: break-all;
                            transition: background 0.15s;
                        "
                        onmouseover="this.style.background='#3a3a3a'"
                        onmouseout="this.style.background='#2a2a2a'"
                    >
                        ${n.label}
                        <div style="color:#888; font-size:11px; margin-top:2px;">${n.id}</div>
                    </div>
                `).join("")}
            </div>
        `;
    }

    function showPanel(nodeId) {
        const connectedEdges = network.getConnectedEdges(nodeId);
        const allEdges = edges.get(connectedEdges);

        const parents = [];
        const children = [];

        allEdges.forEach(edge => {
            if (edge.to === nodeId) {
                const n = nodes.get(edge.from);
                if (n) parents.push(n);
            } else if (edge.from === nodeId) {
                const n = nodes.get(edge.to);
                if (n) children.push(n);
            }
        });

        const current = nodes.get(nodeId);

        panel.style.display = "block";
        panel.innerHTML = `
            <div style="margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid #333;">
                <div style="color:#888; font-size:11px; margin-bottom:4px;">SELECTED</div>
                <div style="color:white; font-weight:bold; font-size:15px; word-break:break-all;">
                    ${current.label}
                </div>
                <div style="color:#555; font-size:11px; margin-top:4px; word-break:break-all;">
                    ${nodeId}
                </div>
            </div>
            ${buildSection("Parents (depends on this)", parents, "#4a9eff")}
            ${buildSection("Children (this depends on)", children, "#ff6b6b")}
            ${!parents.length && !children.length ?
                '<div style="color:#555;">No connections found.</div>' : ""}
        `;
    }

    function navigateTo(nodeId) {
        network.focus(nodeId, {
            scale: 1.2,
            animation: {
                duration: 600,
                easingFunction: "easeInOutQuad"
            }
        });
        network.selectNodes([nodeId]);
        network.setSelection(
            { nodes: [nodeId] },
            { highlightEdges: true }
        );
        showPanel(nodeId);
    }

    network.on("click", function(params) {
        if (params.nodes.length > 0) {
            navigateTo(params.nodes[0]);
        } else {
            panel.style.display = "none";
            network.unselectAll();
        }
    });

    // --- Custom Tooltip ---
    const tooltip = document.createElement("div");
    tooltip.style.cssText = `
        position: fixed;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 6px;
        padding: 10px 14px;
        font-family: monospace;
        font-size: 13px;
        pointer-events: none;
        z-index: 2000;
        display: none;
        max-width: 300px;
    `;
    document.body.appendChild(tooltip);

    network.on("hoverNode", function(params) {
        const n = nodes.get(params.node);
        const inDeg = (n.size - 10) / 3;
        const parts = params.node.split("/");
        const filename = parts[parts.length - 1];
        const path = params.node;

        tooltip.innerHTML = `
            <div style="color:white; font-weight:bold; font-size:14px;">${filename}</div>
            <div style="color:#888; font-style:italic; font-size:12px; margin-top:3px;">${path}</div>
            <div style="color:#555; font-size:11px; margin-top:6px;">Depended on by: ${Math.round(inDeg)} files</div>
        `;
        tooltip.style.display = "block";
    });

    network.on("blurNode", function() {
        tooltip.style.display = "none";
    });

    document.addEventListener("mousemove", function(e) {
        tooltip.style.left = (e.clientX + 16) + "px";
        tooltip.style.top  = (e.clientY + 16) + "px";
    });
    </script>
    """

    html = html.replace("</body>", navigation_script + "</body>")

    with open(output, "w") as f:
        f.write(html)

    print(f"Graph saved to {output} — open it in your browser.")


if __name__ == "__main__":
    G = build_graph(".")
    print(f"Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")
    render_graph(G)