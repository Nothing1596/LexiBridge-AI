# LexiBridge AI Final Project Summary

## Project Name

LexiBridge AI

## Background

Transnational education courses often use English lectures and materials while students rely on Chinese explanations. The main challenge is not simple word translation; it is aligning professional concepts across English and Chinese course knowledge.

## Original Problem

The early idea resembled a bilingual translation website. During iteration, the team found that direct translation cannot solve evidence traceability, course context, teacher workload, and terminology quality control.

## Project Shift

The project shifted from an AI translation tool to an AI retrieval, translation, and evidence alignment platform.

## Core Users

- English and Chinese course teachers.
- Students in transnational education programs.
- Local administrators and pilot owners.

## Core Capabilities

- Multi-format document parsing.
- Image text OCR.
- Formula OCR architecture and FormulaBlock storage.
- Course and personal knowledge bases.
- Evidence retrieval with hard filters.
- Bilingual terminology alignment.
- Terminology card quality control.
- Student feedback and learning marks.
- Evaluation harness and retrieval regression.
- Pilot feedback loop and iteration backlog.

## Technical Overview

The local MVP uses Flask, SQLite, a single-page HTML/CSS/JS frontend, local jobs, structured services, OpenAPI contract, and local release checks. It supports KnowledgeBaseVersion, KnowledgeSource, KnowledgeChunk, RetrievalBackend, TerminologyCard, AlignmentRun, EvaluationRun, PilotFeedback, and IterationBacklogItem.

## Current Version Boundary

The system is local pilot-ready. It is not production-ready. Production would require PostgreSQL, object storage, production queue, live provider governance, formal privacy policy, HTTPS, monitoring, and backup drills.

## Pilot Readiness

The repository now includes demo data, runbooks, manuals, metrics, feedback templates, pilot report templates, and final presentation materials.

## Next Plan

- Run a small real-course pilot with authorized materials.
- Expand teacher-reviewed evaluation sets.
- Replace local demo retrieval with evaluated production retrieval.
- Complete production database, object storage, and queue migration.
