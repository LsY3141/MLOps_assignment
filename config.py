from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    .env 파일로부터 환경 변수를 로드하고 관리하는 설정 클래스.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

    AWS_REGION: str
    S3_BUCKET_NAME: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:
        """
        데이터베이스 연결을 위한 전체 URL을 생성합니다.
        """
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# 설정 객체 인스턴스 생성. 애플리케이션 전역에서 이 객체를 import하여 사용합니다.
settings = Settings()
