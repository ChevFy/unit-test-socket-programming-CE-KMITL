#!/usr/bin/env python3
"""
Automated test runner for Docker environment
Usage:
    python run_test.py <test_number|all> [--file <path>]

Examples:
    python run_test.py 1                    # Run test 1 with auto-generated file
    python run_test.py all                  # Run all tests
    python run_test.py 3 --file myfile.pdf  # Run test 3 with custom file
"""

import sys
import subprocess
import time
import hashlib
import json
from pathlib import Path
import threading
import queue

# ANSI color codes
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color

# Load configuration
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)


def colored(text, color):
    """Return colored text"""
    return f"{color}{text}{NC}"


def read_stream(stream, queue_obj, prefix, color):
    """Read lines from stream in background thread"""
    try:
        for line in iter(stream.readline, ""):
            if line:
                queue_obj.put((prefix, color, line.rstrip()))
    except:
        pass
    finally:
        queue_obj.put(None)  # Signal EOF


def run_command(cmd, capture=True, check=False):
    """Run a shell command"""
    try:
        if capture:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, check=check)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), check=check)
            return result.returncode == 0, "", ""
    except subprocess.CalledProcessError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", str(e)


def docker_exec(container, command, capture=True):
    """Execute command in Docker container"""
    cmd = ["docker", "exec", container] + (command if isinstance(command, list) else command.split())
    return run_command(cmd, capture=capture)


def setup_network_conditions(test_num):
    """Apply network conditions from config"""
    print("Setting up network conditions...")

    # Find test config
    test_config = next((t for t in CONFIG["tests"] if t["id"] == test_num), None)
    if not test_config:
        print(colored(f"Error: Test {test_num} not found in config", RED))
        return False

    print(f"Test: {test_config['name']}")

    # Apply network conditions to each container
    for container_name in ["urft_server", "urft_client"]:
        container_key = "server" if container_name == "urft_server" else "client"
        conditions = test_config["network_conditions"][container_key]

        delay = conditions.get("delay", "null")
        loss = conditions.get("loss", "null")
        duplicate = conditions.get("duplicate", "null")
        reorder = conditions.get("reorder", "null")

        # Convert None to 'null'
        delay = delay if delay else "null"
        loss = loss if loss else "null"
        duplicate = duplicate if duplicate else "null"
        reorder = reorder if reorder else "null"

        cmd = f"sh /app/scripts/network_setup.sh {delay} {loss} {duplicate} {reorder}"
        success, _, _ = docker_exec(container_name, cmd, capture=False)
        if not success:
            print(f"Warning: Failed to setup network for {container_name}")

    return True


def cleanup_test_files():
    """Clean up previous test files"""
    print("Cleaning up previous test files...")
    docker_exec("urft_client", ["sh", "-c", "rm -f /app/test/test_file_*mb.bin"], capture=False)
    docker_exec("urft_server", ["sh", "-c", "rm -rf /app/recived/*"], capture=False)


def create_test_file(size_mb):
    """Create test file in container"""
    filename = f"test_file_{size_mb}mb.bin"
    print(f"Creating {size_mb}MB test file...")

    docker_exec("urft_client", ["mkdir", "-p", "/app/test"], capture=False)
    python_cmd = [
        "python",
        "-c",
        f"import os; " f"filepath = '/app/test/{filename}'; " f"f = open(filepath, 'wb'); " f"[f.write(os.urandom(1024*1024)) for _ in range({size_mb})]; " f"f.close(); " f"print(filepath)",
    ]

    success, stdout, _ = docker_exec("urft_client", python_cmd, capture=True)
    if success:
        print(f"Created: {stdout}")
    return filename if success else None


def use_custom_file(host_filepath):
    """Copy custom file from host to container /app/tmp/"""
    filepath = Path(host_filepath)

    if not filepath.exists():
        print(colored(f"Error: File not found: {filepath}", RED))
        return None

    filename = filepath.name
    file_size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Using custom file: {filename} ({file_size_mb:.2f} MB)")

    # Ensure /app/test exists in both containers
    docker_exec("urft_client", ["mkdir", "-p", "/app/test"], capture=False)

    # Copy file to client container
    container_path = f"urft_client:/app/test/{filename}"
    try:
        subprocess.run(["docker", "cp", str(filepath), container_path], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(colored(f"Error copying file to urft_client: {e}", RED))
        return None

    print(f"Copied to: /app/test/{filename}")
    return filename


def calculate_md5(container, filepath):
    """Calculate MD5 hash of a file in container"""
    cmd = f"md5sum {filepath}"
    success, output, _ = docker_exec(container, cmd, capture=True)
    if success and output:
        # md5sum output format: "hash  filename"
        return output.split()[0]
    return None


def calculate_md5_local(filepath):
    """Calculate MD5 hash of a file on host filesystem"""
    try:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None


def cleanup_server():
    """Kill any lingering server processes"""
    python_cmd = """
import os, signal
for pid in os.listdir('/proc'):
    if pid.isdigit() and int(pid) != 1 and int(pid) != os.getpid():
        try:
            with open(f'/proc/{pid}/cmdline', 'r') as f:
                if 'urft_server.py' in f.read():
                    os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass
"""
    docker_exec("urft_server", ["python", "-c", python_cmd], capture=False)


def cleanup_client():
    """Kill any lingering client processes"""
    python_cmd = """
import os, signal
for pid in os.listdir('/proc'):
    if pid.isdigit() and int(pid) != 1 and int(pid) != os.getpid():
        try:
            with open(f'/proc/{pid}/cmdline', 'r') as f:
                if 'urft_client.py' in f.read():
                    os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass
"""
    docker_exec("urft_client", ["python", "-c", python_cmd], capture=False)


def run_single_test(test_num, custom_file=None):
    """Run a single test - Get test configuration from config.json"""
    test_config = next((t for t in CONFIG["tests"] if t["id"] == test_num), None)
    if not test_config:
        print(colored(f"Error: Test {test_num} not found in config.json", RED))
        return False

    file_size = test_config["file_size_mb"]
    timeout = test_config["timeout"]
    points = test_config["points"]

    print(f"Configuration: {file_size}MB file, {timeout}s timeout, {points} points")
    print(f"Description: {test_config['name']}")

    print("\nNetwork Conditions:")
    for role in ["client", "server"]:
        conds = test_config["network_conditions"].get(role, {})
        params = [f"{k}={v}" for k, v in conds.items() if v]
        print(f"  {role.capitalize()}: {', '.join(params) if params else 'Normal'}")

    # Setup network conditions
    if not setup_network_conditions(test_num):
        return False

    # Clean up previous test
    cleanup_test_files()

    # Create or use test file
    if custom_file:
        filename = use_custom_file(custom_file)
        if not filename:
            print(colored("✗ Failed to use custom file", RED))
            return False
    else:
        filename = create_test_file(file_size)
        if not filename:
            print(colored("✗ Failed to create test file", RED))
            return False

    # Cleanup server and client
    cleanup_server()
    cleanup_client()

    # Calculate original MD5
    original_path = f"/app/test/{filename}"
    original_md5 = calculate_md5("urft_client", original_path)
    print(f"Original MD5:  {original_md5}")

    # Run client transfer
    print("\n" + colored("=" * 70, YELLOW))
    print(colored("Starting file transfer...", YELLOW))
    print(colored("=" * 70, YELLOW))

    server_cmd = ["python", "-u", "/app/src/urft_server.py", "0.0.0.0", str(CONFIG["server"]["port"])]
    client_cmd = ["python", "-u", "/app/src/urft_client.py", original_path, CONFIG["docker"]["server_ip"], str(CONFIG["server"]["port"])]

    # Start client with output visible
    try:
        # Start server process in background
        server_proc = subprocess.Popen(["docker", "exec", "urft_server"] + server_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        time.sleep(1)  # Wait for server to bind

        # Start client process
        client_proc = subprocess.Popen(["docker", "exec", "urft_client"] + client_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        # Create queue for output and start reader threads
        output_queue = queue.Queue()
        server_thread = threading.Thread(target=read_stream, args=(server_proc.stdout, output_queue, "[SERVER] ", GREEN), daemon=True)
        client_thread = threading.Thread(target=read_stream, args=(client_proc.stdout, output_queue, "[CLIENT] ", YELLOW), daemon=True)

        server_thread.start()
        client_thread.start()

        # Read both outputs in real-time
        start_time = time.time()
        client_done = False
        server_done = False
        eof_count = 0

        try:
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    client_proc.kill()
                    print(colored("\n⚠ Transfer timed out", YELLOW))
                    break

                # Check if client finished
                if client_proc.poll() is not None and not client_done:
                    client_done = True

                # Read available output (non-blocking)
                try:
                    item = output_queue.get(timeout=0.1)
                    if item is None:
                        eof_count += 1
                        if eof_count >= 2:  # Both streams closed
                            break
                    else:
                        prefix, color, line = item
                        print(colored(prefix, color) + line)
                        if "File transfer completed." in line and prefix == "[SERVER] ":
                            server_done = True
                except queue.Empty:
                    pass

                if client_done and server_done:
                    break

        except KeyboardInterrupt:
            client_proc.kill()
            server_proc.kill()
            cleanup_server()
            raise

        # Stop server process
        server_proc.kill()
        server_proc.wait()
        cleanup_server()
        cleanup_client()

        print(colored("\n" + "=" * 70, YELLOW))

    except Exception as e:
        print(colored(f"Error running client: {e}", RED))
        return False

    # Give a bit more time for cleanup
    time.sleep(2)

    # Verify file transfer
    print(colored("\n" + "=" * 70, YELLOW))
    print(colored("Verifying file transfer...", YELLOW))
    print(colored("=" * 70, YELLOW))

    # Copy file from recived to temp for verification
    received_dir = Path(__file__).parent.parent / "recived"
    temp_dir = Path(__file__).parent.parent / "temp"
    temp_dir.mkdir(exist_ok=True)

    # List received files (copy from recived folder)
    if received_dir.exists():
        files = list(received_dir.glob("*"))
        files = [f for f in files if f.is_file()]
        if files:
            print("\nReceived files:")
            for f in files:
                print(f"  {f.name}")
                # Copy to temp folder
                import shutil

                shutil.copy(f, temp_dir / f.name)

    # Calculate received MD5 (from temp folder)
    received_file_path = temp_dir / filename
    if received_file_path.exists():
        received_md5 = calculate_md5_local(received_file_path)
    else:
        received_md5 = None

    print(f"\nOriginal MD5: {original_md5}")
    print(f"Received MD5: {received_md5 if received_md5 else 'FILE NOT FOUND'}")

    # Check if test passed
    print(colored("\n" + "=" * 70, YELLOW))
    if received_md5 and original_md5 == received_md5:
        print(colored(f"✓ Test {test_num} PASSED - File transferred successfully!", GREEN))
        print(colored("=" * 70, YELLOW))
        return True
    else:
        if not received_md5:
            print(colored(f"✗ Test {test_num} FAILED - File not received", RED))
        else:
            print(colored(f"✗ Test {test_num} FAILED - File corrupted (MD5 mismatch)\n", RED))
            print(colored("Detailed Byte Analysis:", YELLOW))
            host_original_path = Path(__file__).parent.parent / "test" / filename
            try:
                with open(host_original_path, "rb") as f1, open(received_file_path, "rb") as f2:
                    d1 = f1.read()
                    d2 = f2.read()
                    print(f"  Expected Size: {len(d1)} bytes")
                    print(f"  Received Size: {len(d2)} bytes")
                    if len(d1) != len(d2):
                        diff = len(d2) - len(d1)
                        sign = "+" if diff > 0 else ""
                        print(colored(f"  Size differs by {sign}{diff} bytes!", RED))

                    for i in range(min(len(d1), len(d2))):
                        if d1[i] != d2[i]:
                            print(colored(f"  First mismatch at byte offset {i} (0x{i:04X})", RED))
                            print(f"    Expected: 0x{d1[i]:02X}")
                            print(f"    Received: 0x{d2[i]:02X}")
                            packet_approx = i / (10240 - 2)
                            print(f"    Approximate packet index: {packet_approx:.2f}")
                            break
            except Exception as e:
                print(f"  Could not run detailed analysis: {e}")

        print(colored("-" * 70, YELLOW))
        print(colored("Failed Test Configuration:", YELLOW))
        print(f"  Reproduce : python scripts/run_test.py {test_num}")
        print(f"  File size : {file_size}MB")
        print(f"  Timeout   : {timeout}s")
        print(f"  Desc      : {test_config['name']}")
        for role in ["client", "server"]:
            conds = test_config["network_conditions"].get(role, {})
            params = [f"{k}={v}" for k, v in conds.items() if v]
            print(f"  {role.capitalize()}    : {', '.join(params) if params else 'Normal'}")

        print(colored("=" * 70, YELLOW))
        return False


def start_containers():
    """Start Docker containers"""
    print("Starting Docker containers...")
    # Run from project root, docker-compose.yml is in root
    script_dir = Path(__file__).parent.parent  # Go to project root
    compose_file = script_dir / "docker-compose.yml"
    run_command(f"docker compose -f {compose_file} up -d", capture=False)
    print("Waiting for containers to be ready...")
    time.sleep(3)


def run_all_tests():
    """Run all 8 test cases"""
    passed = 0
    failed = 0

    for test_num in range(1, 9):
        if run_single_test(test_num):
            passed += 1
        else:
            failed += 1
        time.sleep(2)

    # Print summary
    print(f"\n{colored('='*70, YELLOW)}")
    print(colored("Test Summary", YELLOW))
    print(f"{colored('='*70, YELLOW)}")
    print(colored(f"Passed: {passed}", GREEN))
    print(colored(f"Failed: {failed}", RED))
    print(f"Total:  8")
    print(f"{colored('='*70, YELLOW)}\n")

    return failed == 0


def main():
    print(f"\n{colored('='*70, YELLOW)}")
    print(colored("UDP Reliable File Transfer - Test Runner", YELLOW))
    print(f"{colored('='*70, YELLOW)}\n")

    if len(sys.argv) < 2:
        print("Usage: python run_test.py <test_number|all> [--file <path>]")
        print("\nExamples:")
        print("  python run_test.py 1              # Run test 1 with auto-generated file")
        print("  python run_test.py all            # Run all tests")
        print("  python run_test.py 3 --file myfile.bin  # Run test 3 with custom file")
        sys.exit(1)

    test_arg = sys.argv[1]
    custom_file = None

    # Check for --file argument
    if len(sys.argv) > 2 and sys.argv[2] == "--file":
        if len(sys.argv) < 4:
            print(colored("Error: --file requires a file path", RED))
            sys.exit(1)
        custom_file = sys.argv[3]

    # Start containers
    start_containers()

    # Run tests
    if test_arg.lower() == "all":
        if custom_file:
            print(colored("Warning: --file ignored when running all tests", YELLOW))
        success = run_all_tests()
    else:
        try:
            test_num = int(test_arg)
            test_ids = [t["id"] for t in CONFIG["tests"]]
            if test_num in test_ids:
                success = run_single_test(test_num, custom_file)
            else:
                print(colored(f"Error: Test number must be one of {test_ids}", RED))
                sys.exit(1)
        except ValueError:
            print(colored("Error: Invalid test number", RED))
            sys.exit(1)

    print("\nTest run completed!")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
