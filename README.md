# Autonomous Personal Knowledge Management System (PKMS)

An intelligent, non-generative Personal Knowledge Management System (PKMS) designed for semantic search, graph exploration, and learning analytics. The platform helps you organize, connect, and analyze your documents and knowledge without relying on text generation.

## Features

- **Document Processing**: Automatic extraction and parsing of various document formats (PDFs, DOCX, Markdown, etc.).
- **Semantic Search**: Powered by ChromaDB and Sentence Transformers for meaning-based search capabilities.
- **Knowledge Graph**: Explores relationships between concepts, technologies, projects, and people using Neo4j.
- **Learning Analytics**: Track knowledge acquisition, document relationships, and structural insights.
- **Background Processing**: Asynchronous tasks handled seamlessly with Celery and Redis.
- **OCR Capabilities**: Text extraction from images using PyTesseract.
- **Interactive Graph Visualization**: Explore connections visually using Cytoscape.js.

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (Relational), Neo4j (Graph), ChromaDB (Vector Store)
- **Task Queue**: Celery + Redis
- **Machine Learning & NLP**: SpaCy, SentenceTransformers, Scikit-learn
- **Data Extraction**: PyPDF, pdfplumber, python-docx, trafilatura
- **Authentication**: JWT & bcrypt

### Frontend
- **Framework**: React 18 + Vite + TypeScript
- **State Management**: Zustand
- **Data Fetching**: React Query (@tanstack/react-query)
- **Graph Visualization**: Cytoscape.js
- **Routing**: React Router DOM
- **UI Components**: Lucide React, React Dropzone

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js (v18+ recommended)
- NPM or Yarn

### 1. Configuration Setup

Before running the application, you need to set up the backend environment variables.

```bash
# Copy the example environment file
cp backend/.env.example backend/.env
```

Open `backend/.env` and ensure you set a secure string for `JWT_SECRET`:
```env
JWT_SECRET="your_super_secret_random_string_here"
```

### 2. Run the Backend & Infrastructure (Docker)

The easiest way to start the backend, databases, and worker services is via Docker Compose. From the root of the project:

```bash
docker-compose up --build
```

This will spin up:
- PostgreSQL (Port 5432)
- Redis (Port 6379)
- Neo4j (Ports 7474, 7687)
- FastAPI Backend (Port 8000)
- Celery Worker & Beat Scheduler

*Note: The API is configured to automatically run database migrations on startup.*

### 3. Run the Frontend (Local Environment)

The frontend is not containerized by default and needs to be run locally. Open a new terminal window:

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

The frontend will be available at [http://localhost:5173](http://localhost:5173). The API requests are automatically proxied to the backend on `localhost:8000`.

## Project Structure

```
.
├── backend/                  # FastAPI Application
│   ├── app/                  # Main application code (API, Core, DB, Services, Workers)
│   ├── tests/                # Pytest suites
│   ├── alembic/              # Database migrations
│   ├── Dockerfile            # Container configuration
│   ├── pyproject.toml        # Python dependencies
│   └── ...
├── frontend/                 # React UI Application
│   ├── src/                  # React components, pages, stores, hooks
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite configuration
│   └── ...
└── docker-compose.yml        # Orchestration for infrastructure and backend services
```

## Authentication
Authentication is handled via JWT. Create users through the frontend UI or via the exposed API endpoints. The application will use these credentials for both standard API calls and graph analytics.

## Contributing
- The backend relies heavily on type hints and strict mypy configuration.
- Frontend state is strictly managed; refer to `Zustand` and `React Query` implementations for adding new features.
