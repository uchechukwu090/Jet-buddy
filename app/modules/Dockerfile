# Start from a clean Python base
FROM python:3.10

# Set working directory inside the container
WORKDIR /app

# Copy your code
COPY . .

# Install dependencies (and upgrade pip for good measure)
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose the port your app runs on
EXPOSE 10000

# Start the app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
