# LabScribe 🧪  

> An electronic lab notebook (ELN) designed to maximize R&D efficiency with simple, intuitive operation.  

## Overview 📖  

`LabScribe` is a modern electronic lab notebook (ELN) currently under development as part of a larger project aimed at building a future Laboratory Information Management System (LIMS).  

At present, it provides core ELN functionality that allows you to intuitively record daily experiments in a modular format. Future plans include AI-powered summarization, search, and experiment suggestion features, as well as integration with project management tools such as KPI/resource dashboards and Gantt charts.  

## ✨ Features  

* **Module-based editing:** Add and arrange modules for objectives, conditions, results, discussion, charts, tables, and more—tailored to your recording needs.  
* **Chart creation:** Paste data directly from your clipboard to instantly generate charts, with support for multiple data columns.  
* **Table creation:** Quickly create simple tables by pasting data from the clipboard.  
* **Markdown & Mermaid support:** Use `Markdown` for flexible text formatting and `Mermaid` syntax for diagram creation.  
* **Intuitive UI:** Rearrange modules via drag-and-drop, or delete them by dragging to the trash area—no menus required.  

## 🚀 Getting Started  

To run this application, you’ll need Python and Node.js.  

### 1. Prerequisites  

* **Python 3.10** or higher  
* **Node.js** (required for rendering `Mermaid` diagrams)  

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

### 3. Run  

```sh
python main.py
``` 

## Usage ✍️    
* **Adding modules:** Drag the desired module from the left panel into the central editing area.  
* **Creating charts:** In a `Chart` module, click `Paste Data from Clipboard` to generate a chart from clipboard data (comma- or tab-separated). Data is recognized in the form `x, y1, y2, ...`.  
* **Resizing charts:** Drag the gray bar below the chart to adjust its height.  
* **Deleting modules:** Drag unwanted modules to the `Trash` area at the lower left.  

## ⚠️ Known Issues  

* Rendering may slow down when previewing large or complex Markdown content.  

## 🗺️ Roadmap  

* [ ] AI-powered summarization, search, and experiment suggestion  
* [ ] KPI/resource dashboard  
* [ ] Gantt chart integration  
* [ ] Thumbnail previews for saved notes  
* [ ] Performance improvements  
