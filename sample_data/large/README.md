# Large Sample Dataset

Generated for stress testing the GradePulse ingestion pipeline.

## Statistics

- **Students:** 56
- **Content items:** 24
- **Schools:** 3
- **Grade levels:** JSS1-SSS3

## Schools

- **LAGOS MODEL SCHOOL**: JSS1A, JSS1B, JSS2A, JSS2B, SSS1A, SSS1B
- **ABUJA PREP ACADEMY**: JSS1A, JSS2A, SSS1A, SSS2A
- **PORT HARCOURT COLLEGE**: JSS1A, JSS2A, JSS3A, SSS1A, SSS2A, SSS3A

## Usage

```bash
# Ingest all data
python ingest.py --students large_students.csv --content large_content.csv

# Validate only
python ingest.py --validate-only --students large_students.csv --content large_content.csv

# Dry run
python ingest.py --dry-run --students large_students.csv --content large_content.csv
```
