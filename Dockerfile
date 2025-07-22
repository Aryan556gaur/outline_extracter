# Stage 1: Builder - Install dependencies and download models
FROM --platform=linux/amd64 python:3.10-slim-bookworm AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required by PyMuPDF
# libopenjp2-7 for JPEG 2000 support, libjbig2dec0 for JBIG2 support
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libopenjp2-7 \
    libjbig2dec0 \
    build-essential \
    pkg-config \
    git && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the model download script and execute it
# NOTE: For Round 1A only, this script is not strictly necessary as it downloads NLP models
# used in Round 1B. However, it's included for consistency with the full solution structure.
COPY download_models.py .
RUN python download_models.py

# Stage 2: Final - Create a smaller runtime image
FROM --platform=linux/amd64 python:3.10-slim-bookworm AS final

# Set working directory
WORKDIR /app

# Install only runtime system dependencies for PyMuPDF if not already present in slim image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libopenjp2-7 \
    libjbig2dec0 && \
    rm -rf /var/lib/apt/lists/*

# Copy only the necessary Python packages from the builder stage
# This helps keep the final image size small
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the pre-downloaded models (if any, from download_models.py)
COPY --from=builder /app/models /app/models

# Copy the application code
COPY pdf_processor.py .
COPY main.py .

# Create input and output directories
RUN mkdir -p input output

# Set the command to run the main application script
# This command will be executed when the container starts
CMD ["python", "main.py"]
