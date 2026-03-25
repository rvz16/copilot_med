#!/usr/bin/env python3
"""
Create a ClearML task for serving Qwen3.5-9B via vLLM.

Usage:
    python scripts/create_clearml_qwen3_task.py --queue high_q
    python scripts/create_clearml_qwen3_task.py --queue high_q --port 8001
    python scripts/create_clearml_qwen3_task.py --queue high_q --model Qwen/Qwen3.5-9B --port 8001
"""

from clearml import Task

DEFAULT_DOCKER_IMAGE = "vllm/vllm-openai:v0.8.5.post1"
DEFAULT_DOCKER_ARGS = "--entrypoint= --network=host --shm-size=16g --gpus all"

VLLM_SERVE_SCRIPT = r"""
import subprocess
import shutil
import os

model = "{model_name}"
port = {port}
gpu_memory_utilization = {gpu_memory_utilization}
max_model_len = {max_model_len}
tensor_parallel_size = {tensor_parallel_size}

# Enable verbose logging to see engine core errors
os.environ["VLLM_LOGGING_LEVEL"] = "DEBUG"
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

vllm_bin = shutil.which("vllm")
if vllm_bin:
    cmd = [
        vllm_bin, "serve", model,
        "--port", str(port),
        "--dtype", "bfloat16",
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--tensor-parallel-size", str(tensor_parallel_size),
        "--trust-remote-code",
        "--enforce-eager",
    ]
else:
    cmd = [
        "/usr/bin/python3", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--port", str(port),
        "--dtype", "bfloat16",
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--tensor-parallel-size", str(tensor_parallel_size),
        "--trust-remote-code",
        "--enforce-eager",
    ]

print(f"Starting vLLM server: {{' '.join(cmd)}}")
print(f"CUDA_VISIBLE_DEVICES: {{os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}}")

# Upload output as artifact so we can inspect errors in ClearML UI
from clearml import Task as _Task
_task = _Task.current_task()

log_path = "/tmp/vllm_output.log"
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
with open(log_path, "w") as log_file:
    for line in proc.stdout:
        print(line, end="", flush=True)
        log_file.write(line)
rc = proc.wait()

if _task:
    _task.upload_artifact("vllm_output_log", artifact_object=log_path)

if rc != 0:
    # Also print last 100 lines for quick inspection
    with open(log_path) as f:
        lines = f.readlines()
        print("\\n=== LAST 100 LINES OF VLLM OUTPUT ===")
        for l in lines[-100:]:
            print(l, end="")
    raise SystemExit(f"vLLM exited with code {{rc}}")
"""

DOCKER_BASH_SETUP = r"""
echo "=== GPU Info ==="
nvidia-smi
nvidia-smi -L
echo "=== Installing/upgrading deps ==="
pip install clearml
pip install --upgrade vllm transformers
echo "================"
"""


def create_qwen3_task(
    project_name: str = "llm-tts-service",
    task_name: str = "vLLM Qwen3.5-9B",
    queue_name: str = "high_q_2xA100_80",
    model_name: str = "Qwen/Qwen3.5-9B",
    port: int = 8001,
    gpu_memory_utilization: float = 0.90,
    max_model_len: int = 4096,
    tensor_parallel_size: int = 1,
    use_docker: bool = True,
):
    # Write the inline serve script
    script_content = VLLM_SERVE_SCRIPT.format(
        model_name=model_name,
        port=port,
        gpu_memory_utilization=gpu_memory_utilization,
        max_model_len=max_model_len,
        tensor_parallel_size=tensor_parallel_size,
    )

    import tempfile
    import os

    script_path = os.path.join(tempfile.gettempdir(), "vllm_serve_entry.py")
    with open(script_path, "w") as f:
        f.write(script_content)

    docker_args = DEFAULT_DOCKER_ARGS

    task = Task.create(
        project_name=project_name,
        task_name=task_name,
        repo="https://github.com/rvz16/copilot_med.git",
        branch="dev-victor",
        script=script_path,
        docker=f"{DEFAULT_DOCKER_IMAGE} {docker_args}" if use_docker else None,
        docker_bash_setup_script=DOCKER_BASH_SETUP if use_docker else None,
        packages=[],
    )

    print(f"Created task: {task.id}")
    Task.enqueue(task, queue_name=queue_name)
    print(f"Enqueued to: {queue_name}")
    print(f"\nOnce running, endpoint: http://<AGENT_IP>:{port}/v1")
    print(f"Model: {model_name}")
    print(f"Max context length: {max_model_len}")
    print(f"\nvLLM flags: --dtype auto --tensor-parallel-size {tensor_parallel_size} --gpu-memory-utilization {gpu_memory_utilization}")
    print("\nUsage from other scripts:")
    print(f'  client = OpenAI(base_url="http://<AGENT_IP>:{port}/v1", api_key="unused")')
    print(f'  client.chat.completions.create(model="{model_name}", messages=[...])')
    return task


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create ClearML task for vLLM Qwen3.5-9B endpoint"
    )
    parser.add_argument("--project", default="llm-tts-service")
    parser.add_argument("--name", default="vLLM Qwen3.5-9B")
    parser.add_argument("--queue", default="high_q_2xA100_80")
    parser.add_argument("--model", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--gpu-mem", type=float, default=0.90,
                        help="GPU memory utilization (0.0-1.0)")
    parser.add_argument("--max-model-len", type=int, default=4096,
                        help="Max context length (lower = faster, less VRAM)")
    parser.add_argument("--tp", type=int, default=1,
                        help="Tensor parallel size (number of GPUs)")
    parser.add_argument("--no-docker", action="store_true", help="Run without Docker")
    args = parser.parse_args()

    create_qwen3_task(
        project_name=args.project,
        task_name=args.name,
        queue_name=args.queue,
        model_name=args.model,
        port=args.port,
        gpu_memory_utilization=args.gpu_mem,
        max_model_len=args.max_model_len,
        tensor_parallel_size=args.tp,
        use_docker=not args.no_docker,
    )
