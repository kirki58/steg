import os
import zipfile
from PIL import Image

def create_zip_from_dir(dir_path, zip_name):
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dir_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, start=dir_path)
                zf.write(full_path, arcname)
    print(f"Created zip from directory '{dir_path}': {zip_name}")

def bytes_to_bits(data):
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_bytes(bits):
    bytes_out = bytearray()
    for b in range(0, len(bits), 8):
        byte = 0
        for i in range(8):
            if b + i < len(bits):
                byte = (byte << 1) | bits[b + i]
            else:
                byte <<= 1
        bytes_out.append(byte)
    return bytes(bytes_out)

def embed_bits_in_image(img_path, bits, output_path, chunk_index, total_chunks):
    img = Image.open(img_path)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    pixels = img.load()

    width, height = img.size
    num_pixels = width * height

    # Prepare 96-bit header: chunk_index (32 bits), total_chunks (32 bits), data length in bits (32 bits)
    header_bits = []
    for val in (chunk_index, total_chunks, len(bits)):
        for i in range(31, -1, -1):
            header_bits.append((val >> i) & 1)

    full_bits = header_bits + bits
    if len(full_bits) > num_pixels:
        raise ValueError(f"Image '{img_path}' not large enough to hold data chunk")

    bit_idx = 0
    for y in range(height):
        for x in range(width):
            if bit_idx >= len(full_bits):
                break
            r, g, b = pixels[x, y]
            r = (r & 0xFE) | full_bits[bit_idx]  # Embed bit in red LSB
            pixels[x, y] = (r, g, b)
            bit_idx += 1
        if bit_idx >= len(full_bits):
            break

    img.save(output_path)
    print(f"Embedded chunk {chunk_index + 1}/{total_chunks} in {output_path}")

def extract_bits_from_image(img_path):
    img = Image.open(img_path)
    pixels = img.load()
    width, height = img.size
    num_pixels = width * height

    bits = []
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            bits.append(r & 1)

    # Extract header: first 96 bits
    header_bits = bits[:96]

    def bits_to_int(bits_slice):
        val = 0
        for bit in bits_slice:
            val = (val << 1) | bit
        return val

    chunk_index = bits_to_int(header_bits[0:32])
    total_chunks = bits_to_int(header_bits[32:64])
    data_length = bits_to_int(header_bits[64:96])

    data_bits = bits[96:96 + data_length]
    data_bytes = bits_to_bytes(data_bits)

    return chunk_index, total_chunks, data_bytes

def embed_zip_of_dir_into_images(dir_path, image_list, output_folder, zip_name):
    # 1. Create zip archive from directory
    create_zip_from_dir(dir_path, zip_name)

    # 2. Read zip bytes
    with open(zip_name, 'rb') as f:
        zip_data = f.read()

    zip_bits = bytes_to_bits(zip_data)

    # 3. Calculate capacity per image (pixels - 96 bits for header)
    capacities = []
    for img_path in image_list:
        img = Image.open(img_path)
        w, h = img.size
        capacities.append(w * h - 96)

    total_capacity = sum(capacities)
    if len(zip_bits) > total_capacity:
        raise ValueError("Not enough capacity in images to store zip data")

    # 4. Split zip bits according to capacity per image
    chunks = []
    bit_pos = 0
    for cap in capacities:
        chunk_bits = zip_bits[bit_pos:bit_pos + cap]
        chunks.append(chunk_bits)
        bit_pos += cap

    total_chunks = len(chunks)
    os.makedirs(output_folder, exist_ok=True)

    # 5. Embed chunks into images
    for i, (img_path, chunk_bits) in enumerate(zip(image_list, chunks)):
        out_path = os.path.join(output_folder, f"embedded_{i}.png")
        embed_bits_in_image(img_path, chunk_bits, out_path, i, total_chunks)

def recover_zip_from_images(embedded_images, output_zip_path):
    chunks_dict = {}
    total_chunks = None

    for img_path in embedded_images:
        chunk_index, t_chunks, data_bytes = extract_bits_from_image(img_path)
        chunks_dict[chunk_index] = data_bytes
        if total_chunks is None:
            total_chunks = t_chunks
        print(f"Extracted chunk {chunk_index + 1}/{t_chunks} from {img_path}")

    if total_chunks is None or len(chunks_dict) != total_chunks:
        raise ValueError("Missing chunks, cannot recover full zip")

    # Concatenate chunks by index order
    recovered_data = b''.join(chunks_dict[i] for i in range(total_chunks))

    with open(output_zip_path, 'wb') as f:
        f.write(recovered_data)
    print(f"Recovered zip saved as {output_zip_path}")

def dry_run_encode(dir_path, images):
    print("🔍 Performing dry run...")
    
    # 1. Create temp zip file
    zip_name = "temp_dry_run.zip"
    create_zip_from_dir(dir_path, zip_name)

    # 2. Read zip and convert to bits
    with open(zip_name, "rb") as f:
        zip_data = f.read()
    zip_bits = bytes_to_bits(zip_data)
    total_bits_needed = len(zip_bits)

    # 3. Analyze image capacities
    capacities = []
    total_capacity = 0
    for img_path in images:
        with Image.open(img_path) as img:
            width, height = img.size
            capacity = (width * height - 96)  # bits
            capacities.append((img_path, capacity))
            total_capacity += capacity

    os.remove(zip_name)

    # 4. Print report
    print(f"📁 Directory to embed: {dir_path}")
    print(f"🗜️  Zip size: {len(zip_data)} bytes ({total_bits_needed} bits)")
    print(f"🖼️  Number of images: {len(images)}")
    print(f"🧠 Total image capacity: {total_capacity} bits\n")

    if total_capacity < total_bits_needed:
        print("❌ Not enough capacity. You need more or larger images.")
        bits_needed = total_bits_needed - total_capacity
        print(f"➡️ Short by {bits_needed} bits ({bits_needed // 8} bytes)")
    else:
        print("✅ Enough capacity. Estimated chunking:")
        remaining = total_bits_needed
        for i, (img_path, capacity) in enumerate(capacities):
            used = min(capacity, remaining)
            print(f"  - {os.path.basename(img_path)}: will store {used} bits ({used // 8} bytes)")
            remaining -= used
            if remaining <= 0:
                break
