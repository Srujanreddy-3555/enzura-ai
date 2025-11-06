import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, BinaryIO
import uuid
from datetime import datetime
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        # Central credentials no longer used. Operate per-client only.
        self.s3_client = None

    def generate_s3_key(self, filename: str, user_id: int) -> str:
        """Generate a unique S3 key for the file"""
        timestamp = datetime.utcnow().strftime("%Y/%m/%d")
        unique_id = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(filename)[1]
        return f"calls/{user_id}/{timestamp}/{unique_id}{file_extension}"

    def _client_from_credentials(self, access_key: str, secret_key: str, region: str):
        return boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

    async def upload_file_for_client(self, *, file_content, filename: str, user_id: int, bucket_name: str, region: str, access_key: str, secret_key: str) -> Optional[str]:
        """
        Upload file to S3 (per-client credentials) and return the S3 URL
        Handles both UploadFile objects and regular file-like objects
        """
        logger.info(f"Starting S3 upload for file: {filename}, user: {user_id}")

        s3_client = self._client_from_credentials(access_key, secret_key, region)

        try:
            s3_key = self.generate_s3_key(filename, user_id)
            logger.info(f"Generated S3 key: {s3_key}")
            
            # Handle UploadFile objects from FastAPI
            if hasattr(file_content, 'file'):
                # This is a FastAPI UploadFile object
                logger.info(f"Processing FastAPI UploadFile: {filename}")
                file_obj = file_content.file
                file_size = file_content.size or 0
            elif hasattr(file_content, 'read'):
                # This is a file-like object
                logger.info(f"Processing file-like object: {filename}")
                file_obj = file_content
                # Reset file pointer to beginning
                file_obj.seek(0)
                # Get file size for logging
                file_obj.seek(0, 2)  # Seek to end
                file_size = file_obj.tell()
                file_obj.seek(0)  # Reset to beginning
            else:
                # This might be bytes or string content
                logger.info(f"Processing content as bytes: {filename}")
                if isinstance(file_content, str):
                    file_obj = file_content.encode('utf-8')
                else:
                    file_obj = file_content
                file_size = len(file_obj)
                
                # For bytes content, we need to use upload_fileobj with BytesIO
                import io
                file_obj = io.BytesIO(file_obj)
            
            logger.info(f"Uploading file {filename} ({file_size} bytes) to S3 key: {s3_key}")
            
            # Upload file
            s3_client.upload_fileobj(
                file_obj,
                bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': self._get_content_type(filename),
                    'Metadata': {
                        'original_filename': filename,
                        'user_id': str(user_id),
                        'upload_timestamp': datetime.utcnow().isoformat()
                    }
                }
            )
            
            s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
            logger.info(f"Successfully uploaded {filename} to S3: {s3_url}")
            return s3_url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS S3 ClientError uploading {filename}: {error_code} - {error_message}")
            
            # Provide more specific error messages
            if error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket '{self.bucket_name}' does not exist")
            elif error_code == 'AccessDenied':
                logger.error(f"Access denied to S3 bucket '{self.bucket_name}'")
            elif error_code == 'InvalidAccessKeyId':
                logger.error("Invalid AWS access key ID")
            elif error_code == 'SignatureDoesNotMatch':
                logger.error("AWS signature does not match")
            elif error_code == 'RequestTimeout':
                logger.error("S3 request timed out")
            
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading {filename} to S3: {str(e)}")
            return None

    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        extension = os.path.splitext(filename)[1].lower()
        content_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac'
        }
        return content_types.get(extension, 'application/octet-stream')

    async def delete_file(self, s3_url: str) -> bool:
        """
        Delete file from S3
        """
        if not self.s3_client:
            logger.info(f"Mocking S3 delete for URL: {s3_url}")
            return True

        try:
            # Parse bucket, region, and key from full S3 URL: https://{bucket}.s3.{region}.amazonaws.com/{key}
            parsed = urlparse(s3_url)
            host = parsed.netloc  # {bucket}.s3.{region}.amazonaws.com
            path = parsed.path.lstrip('/')
            parts = host.split('.')
            bucket = parts[0] if parts else ''
            # Region is parts[2] if host like bucket.s3.<region>.amazonaws.com
            region = parts[2] if len(parts) >= 4 else ''

            self.s3_client.delete_object(Bucket=bucket, Key=path)
            logger.info(f"Successfully deleted file from S3: {path}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                logger.warning(f"Delete permission denied for S3 file: {path}. File will remain in S3.")
                return True  # Return True since the operation "succeeded" from our perspective
            else:
                logger.error(f"Failed to delete file from S3: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file: {e}")
            return False

    async def get_file_url(self, s3_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for file access
        """
        if not self.s3_client:
            # Cannot generate presigned URL without a client/creds
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None

    async def download_file(self, s3_url: str) -> Optional[bytes]:
        """
        Download file from S3 and return as bytes
        """
        if not self.s3_client:
            logger.warning(f"S3 client not available, cannot download file: {s3_url}")
            return None

        try:
            # Parse bucket, region, and key from URL
            parsed = urlparse(s3_url)
            host = parsed.netloc
            path = parsed.path.lstrip('/')
            parts = host.split('.')
            bucket = parts[0] if parts else ''
            logger.info(f"Downloading file from S3: {path}")
            
            # Download file as bytes
            response = self.s3_client.get_object(Bucket=bucket, Key=path)
            file_content = response['Body'].read()
            
            logger.info(f"Successfully downloaded file from S3: {path} ({len(file_content)} bytes)")
            return file_content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS S3 ClientError downloading {s3_url}: {error_code} - {error_message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file from S3: {str(e)}")
            return None

    def is_connected(self) -> bool:
        """Check if S3 service is properly connected"""
        return self.s3_client is not None

# Global S3 service instance
s3_service = S3Service()
