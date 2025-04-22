#!/usr/bin/env python3

import os
import random
import subprocess

# Define the path to the convert.py script
SCRIPT_PATH = os.path.expanduser("~/Apps/Scripts/convert.py")

# Function to generate a random number within a specified range
def generate_random_number(min_value, max_value, seed=None):
    if seed is not None:
        random.seed(seed)
    return random.randint(min_value, max_value)

# Function to generate a random float within a specified range
def generate_random_float(max_value, seed=None):
    if seed is not None:
        random.seed(seed)
    return random.uniform(0, float(max_value))

# Function to generate a random hex string of a given length
def generate_random_hex_string(length, seed=None):
    if seed is not None:
        random.seed(seed)
    return ''.join(random.choice('0123456789ABCDEF') for _ in range(length))

# Array of test cases
test_cases = [
    ("ubyte", 255),
    ("ushort", 65535),
    ("uint32", 4294967295),
    ("uint64", 18446744073709551615),
    ("float", 3.4028235e+38),  # max positive float value in scientific notation
    ("doublefloat", 1.7976931348623157e+308),  # max positive double float value in scientific notation
    ("halffloat", 65504)  # max positive half float value
]

# Function to run the convert.py command and return the output
def run_convert_command(value, format_str=None, little_endian=False, swap=False):
    endian_flag = "--little" if little_endian else ""
    swap_flag = "--swap" if swap else ""
    command = f"python3 {SCRIPT_PATH} {value} {f'--{format_str}' if format_str else ''} {endian_flag} {swap_flag}".strip()
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

# Function to perform the tests
def perform_test(format_str, max_value, seed):
    if format_str in ["float", "doublefloat", "halffloat"]:
        value = generate_random_float(max_value, seed)
    else:
        value = generate_random_number(0, max_value, seed)
    
    # Run the Dec to Hex conversion without little-endian flag
    hex_output = run_convert_command(value, format_str, little_endian=False)
    print(f"Dec to Hex: {value} --{format_str} -> {hex_output}")

    # Extract the hex value from the output
    hex_value = hex_output.split(' ')[-1]

    # Run the Hex to Dec conversion without little-endian flag
    dec_output = run_convert_command(f"0x{hex_value}", format_str, little_endian=False)
    print(f"Hex to Dec: 0x{hex_value} --{format_str} -> {dec_output}")
    print("")

    # Run the Dec to Hex conversion with little-endian flag
    hex_output_little = run_convert_command(value, format_str, little_endian=True)
    print(f"Dec to Hex: {value} --{format_str} --little -> {hex_output_little}")

    # Extract the hex value from the output
    hex_value_little = hex_output_little.split(' ')[-1]

    # Run the Hex to Dec conversion with little-endian flag
    dec_output_little = run_convert_command(f"0x{hex_value_little}", format_str, little_endian=True)
    print(f"Hex to Dec: 0x{hex_value_little} --{format_str} --little -> {dec_output_little}")
    print("")

# Function to perform the swap test
def perform_swap_test(seed):
    # Generate random hex strings of different lengths
    lengths = [6, 16, 30]
    for length in lengths:
        hex_string = generate_random_hex_string(length, seed)
        swap_output = run_convert_command(hex_string, swap=True)
        print(f"Swap: {hex_string} -> {swap_output}")
        print("")

# Main function to run the tests
def main():
    seed = random.randint(0, 1000000)  # Generate a random seed
    print(f"Using seed: {seed}\n")

    # Iterate over each test case
    for format_str, max_value in test_cases:
        # Perform test with the same seed for both big-endian and little-endian
        perform_test(format_str, max_value, seed)

    # Perform swap tests
    perform_swap_test(seed)

if __name__ == "__main__":
    main()
