import sys
import os
import string
import datetime
from matplotlib.backends.backend_pdf import PdfPages
import logging as log
import logging.handlers as hdl
from email_campaign_analysis import Campaign_Analysis, validate_inputs as validate_campaign_inputs
from church_analysis import Church_Analysis, validate_inputs as validate_church_inputs
from persona_analysis import Persona_Analysis, validate_inputs as validate_persona_inputs

current_datetime = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")
# Get output and input folders from command line arguments or environment variables
if len(sys.argv) > 2:
    output_dir = sys.argv[1]
    input_dir = sys.argv[2]
else:
    output_dir = os.environ.get("OUTPUT_DIR", os.getcwd())
    output_dir=os.path.join(output_dir, "Output"+str(current_datetime) )
    input_dir = os.environ.get("INPUT_DIR", os.getcwd())

# Create output folder if needed
try:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
except Exception as e:
    print(f"Could not create output folder: {output_dir}. Error: {e}")
    with open(os.path.join(output_dir, "error_summary.txt"), "w") as f:
        f.write(f"Could not create output folder: {output_dir}. Error: {e}")
    sys.exit(1)

# Remove old Analysis.log before setting up logger
log_file = os.path.join(output_dir, 'Analysis.log')
if os.path.exists(log_file):
    os.remove(log_file)

# Set up logger early to log folder issues
logger = log.Logger('flat_file')
logger.setLevel(log.INFO)  # Reduce log verbosity
formatter = log.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = hdl.RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=2)
handler.setFormatter(formatter)
stream_handler = log.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(stream_handler)

# Add a header to the log file
logger.info(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


logger.info(f"Input folder: {input_dir}")
logger.info(f"Output folder: {output_dir}")

# Check input folder
if not os.path.exists(input_dir):
    logger.error(f"Input folder does not exist: {input_dir}")
    with open(os.path.join(output_dir, "error_summary.txt"), "w") as f:
        f.write(f"Input folder does not exist: {input_dir}")
    sys.exit(1)

# Check required input files
required_files = [
    'd4g_account.csv',
    'd4g_opportunity.csv',
    'd4g_address.csv',
    'campaign_monitor_extract.csv',
    'contact_extract.csv',
    'email_tracking_extract.csv',
]
missing_files = [fname for fname in required_files if not os.path.exists(os.path.join(input_dir, fname))]
if missing_files:
    logger.error(f"Missing required input files: {missing_files}")
    with open(os.path.join(output_dir, "error_summary.txt"), "w") as f:
        f.write(f"Missing required input files: {missing_files}")
    sys.exit(1)


pdf_filename="Output_"+str(current_datetime)+".pdf"
pdf = PdfPages(os.path.join(output_dir, pdf_filename))

try:
    Analyzer1 = Persona_Analysis()
    if validate_persona_inputs(logger, input_dir):
        Analyzer1.process_Personas(pdf, logger, output_dir, input_dir)
    else:
        logger.error("Persona analysis validation failed. Skipping persona analysis.")

    Analyzer2 = Campaign_Analysis()
    if validate_campaign_inputs(logger, input_dir):
        Analyzer2.process_campaign(pdf, logger, output_dir, input_dir)
    else:
        logger.error("Campaign analysis validation failed. Skipping campaign analysis.")

    Analyzer3 = Church_Analysis()
    if validate_church_inputs(logger, input_dir):
        Analyzer3.process_ChurchData(pdf, logger, output_dir, input_dir)
    else:
        logger.error("Church analysis validation failed. Skipping church analysis.")
except Exception as e:
    logger.error(f"Critical error: {e}")
    with open(os.path.join(output_dir, "error_summary.txt"), "w") as f:
        f.write(str(e))
finally:
    pdf.close()
    log.shutdown()
