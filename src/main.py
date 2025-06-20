from lsb import *
import argparse as argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(
        description="LSB Steganography: Embed or extract a zip archive into/from images."
    )

    parser.add_argument(
        "-m", "--mode",
        type=str,
        choices=['encode', 'decode', 'dry'],
        help="Mode of operation: encode (hide zip), decode (recover zip), dry (test encode capacity only).",
        required=True
    )

    parser.add_argument(
        "-p", "--path",
        type=str,
        help="Path to the source directory (for encode/dry).",
    )

    parser.add_argument(
        "-i", "--images",
        nargs='+',
        type=str,
        help="List of PNG images to embed data into (for encode/dry) or to extract data from (for decode).",
        required=True
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to save the decoded zip file (only used in decode mode)."
    )

    args = parser.parse_args()

    args.images.sort()
    # Validate image files
    for img in args.images:
        if not os.path.isfile(img):
            parser.error(f"Image file does not exist: {img}")
        if not img.lower().endswith(".png"):
            parser.error(f"Image file must be a PNG: {img}")

    # Additional manual validations
    if args.mode in ['encode', 'dry']:
        if not args.path:
            parser.error("'-p/--path' is required in encode or dry mode.")
        elif not os.path.isdir(args.path):
            parser.error(f"Provided path does not exist or is not a directory: {args.path}")
        
        if args.mode == "dry":
            dry_run_encode(args.path, args.images)
        else:
            print("🔐 Encoding...")
            zip_name = "embedded.zip"
            embed_zip_of_dir_into_images(
                dir_path=args.path,
                output_folder="stego_images",
                zip_name=zip_name,
                image_list=args.images
            )
            
    
    if args.mode == 'decode':
        if not args.output:
            parser.error("'-o/--output' is required in decode mode.")
        elif os.path.exists(args.output):
            print(f"Warning: Output file '{args.output}' already exists and will be overwritten.", file=sys.stderr)
        
        print("🔍 Decoding...")
        recover_zip_from_images(
            embedded_images=args.images,
            output_zip_path=args.output
        )

    return args


if __name__ == '__main__':
    main()
