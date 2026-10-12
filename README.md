# JANGO — Enterprise Document Intelligence Platform

A full-stack AI application that transforms PDF documents into a searchable knowledge base using Retrieval-Augmented Generation (RAG).

## Overview

JANGO allows authenticated users to upload PDF documents and ask natural-language questions about their contents. It retrieves relevant passages and uses a language model to generate context-aware answers.

## Core Features

- PDF upload, validation, text extraction, and chunking
- Embedding generation and vector indexing with ChromaDB
- Retrieval-Augmented Generation for document question answering
- JWT-based authentication and password hashing
- User-scoped document retrieval
- SHA-256 content-based deduplication
- Idempotency handling for repeated upload requests
- SQLAlchemy-based relational persistence
- Background document ingestion
- Configurable AI providers and deployment settings
- Automated backend tests

## Architecture

