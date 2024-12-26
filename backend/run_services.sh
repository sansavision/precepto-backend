#!/bin/bash

# Script: run_services.sh
# Description: Manages backend services by starting, stopping, and streaming logs.
# Usage:
#   ./run_services.sh start    # Start all services
#   ./run_services.sh stop     # Stop all services
#   ./run_services.sh logs     # Stream logs of all services

# Exit immediately if a command exits with a non-zero status
set -e

# Directory containing the backend services (assumes script is in the backend directory)
BACKEND_DIR="$(dirname "$0")"
SERVICES_DIR="$BACKEND_DIR"

# Directories to store log files and PID files
LOG_DIR="$BACKEND_DIR/logs"
PID_DIR="$BACKEND_DIR/pids"

# Create logs and pids directories if they don't exist
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

# Array to hold background process IDs
declare -a PIDS=()

# Function to start a service
start_service() {
    local service_path=$1
    local service_name=$(basename "$service_path")
    local log_file="$LOG_DIR/${service_name}.log"
    local pid_file="$PID_DIR/${service_name}.pid"

    # Check if the service is already running
    if [ -f "$pid_file" ]; then
        local existing_pid
        existing_pid=$(cat "$pid_file")
        if ps -p "$existing_pid" > /dev/null 2>&1; then
            echo "Service '$service_name' is already running with PID $existing_pid. Skipping..."
            return
        else
            echo "Found stale PID file for '$service_name'. Removing..."
            rm -f "$pid_file"
        fi
    fi

    # Determine the main Python script (assumes it's the only .py file in the service directory)
    main_script=$(find "$service_path" -maxdepth 1 -type f -name "*.py" | head -n 1)

    if [ -z "$main_script" ]; then
        echo "No Python script found in $service_path. Skipping..."
        return
    fi

    echo "Starting $service_name..."
    # Run the service in the background and redirect output to the log file
    nohup python "$main_script" > "$log_file" 2>&1 &
    local pid=$!
    echo "$pid" > "$pid_file"
    echo "$service_name started with PID $pid and logging to $log_file"
}

# Function to stop a service
stop_service() {
    local service_path=$1
    local service_name=$(basename "$service_path")
    local pid_file="$PID_DIR/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        echo "PID file for service '$service_name' not found. Is it running?"
        return
    fi

    local pid
    pid=$(cat "$pid_file")

    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo "Service '$service_name' with PID $pid is not running. Removing PID file."
        rm -f "$pid_file"
        return
    fi

    echo "Stopping service '$service_name' with PID $pid..."
    kill "$pid"

    # Wait for the process to terminate
    while ps -p "$pid" > /dev/null 2>&1; do
        sleep 1
    done

    echo "Service '$service_name' has been stopped."
    rm -f "$pid_file"
}

# Function to stream logs of all services
stream_logs() {
    if [ ! -d "$LOG_DIR" ]; then
        echo "Logs directory '$LOG_DIR' does not exist."
        exit 1
    fi

    echo "Streaming logs from all services. Press Ctrl+C to exit."

    # Use tail to follow all .log files in the LOG_DIR
    tail -f "$LOG_DIR"/*.log
}

# Function to display usage information
usage() {
    echo "Usage: $0 {start|stop|logs}"
    exit 1
}

# Ensure exactly one argument is provided
if [ "$#" -ne 1 ]; then
    usage
fi

# Assign the first argument to ACTION
ACTION=$1

case "$ACTION" in
    start)
        echo "Starting all services..."
        for service in "$SERVICES_DIR"/*/; do
            if [ -d "$service" ]; then
                start_service "$service"
            fi
        done
        echo "All services have been started. Logs are available in the 'logs' directory."
        ;;
    stop)
        echo "Stopping all services..."
        for service in "$SERVICES_DIR"/*/; do
            if [ -d "$service" ]; then
                stop_service "$service"
            fi
        done
        echo "All services have been stopped."
        ;;
    logs)
        stream_logs
        ;;
    *)
        usage
        ;;
esac