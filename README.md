# LabScribe 🧪  

> An electronic lab notebook (ELN) designed to maximize R&D efficiency with simple, intuitive operation.  

## Overview 📖  

`LabScribe` is a modern electronic lab notebook (ELN) developed as part of a broader project to build a future Laboratory Information Management System (LIMS).

Currently, it provides core ELN functionality that allows you to record daily experiments in a modular format. It also includes an **AI-powered summarization feature** that connects to a local LLM server (e.g., Ollama). This enables automatic summarization of experimental records. Future plans include AI-powered search and experiment suggestion, along with integration with project management tools such as KPI/resource dashboards.

## ✨ Features  

* **Module-based editing:** Add and arrange modules for objectives, conditions, results, discussion, charts, tables, and more—tailored to your recording needs.  
* **Gantt chart creation:** Visualize project timelines and task dependencies.
* **Chart creation:** Paste data directly from your clipboard to instantly generate charts, with support for multiple data columns.  
* **Table creation:** Quickly create simple tables by pasting data from the clipboard.  
* **Markdown & Mermaid support:** Use `Markdown` for flexible text formatting and `Mermaid` syntax for diagram creation.  
* **Intuitive UI:** Rearrange modules via drag-and-drop, or delete them by dragging to the trash area—no menus required.  
* **AI-powered summarization:** Connect to a local or remote LLM server (such as Ollama) to automatically summarize experiment records. Configuration is managed via `config.py`.

## 🚀 Getting Started  

This application requires Python and Node.js.  

### 1. Prerequisites  

* **Python 3.10** or higher
* **Node.js** (required for rendering `Mermaid` diagrams)
* **LLM server** (e.g., Ollama, or any server that provides a compatible API)

### 2. Installation  

1. **Clone the repository:**  
    ```sh
    git clone https://github.com/your-username/LabScribe.git
    cd LabScribe
    ```  

2. **Install Python dependencies:**  
    ```sh
    pip install -r requirements.txt
    ```  

3. **Install Mermaid CLI** (only if using Mermaid diagrams):  
    ```sh
    npm install -g @mermaid-js/mermaid-cli
    ```  

### 3. Configuration

To enable AI summarization, you can edit `config.py`. The defaults are:

```python
# Ollama API Endpoint
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# Model name used for summary generation
SUMMARY_GENERATOR_MODEL = "gemma3:12b"
```

### 4. Run  

```sh
python main.py
``` 

## Usage ✍️    
* **Adding modules:** Drag the desired module from the left panel into the central editing area.  
* **Creating charts & Gantt charts:** Add the module, input your data, and see the visualization.
* **Resizing charts:** Drag the gray bar below the chart to adjust its height.  
* **Deleting modules:** Drag unwanted modules to the `Trash` area at the lower left.  
* **AI summarization:** After entering experiment records, click the "Generate Summary" button in the Outline panel to generate an AI-powered summary for each module.

## ⚠️ Known Issues  

* Rendering may slow down when previewing large or complex Markdown content.  

## 🗺️ Roadmap  

* [x] Gantt chart integration
* [x] AI-powered summarization (Phase 1: Module summaries)
* [ ] AI-powered search and experiment suggestion  
* [ ] KPI/resource dashboard  
* [ ] Thumbnail previews for saved notes  
* [ ] Performance improvements  
