
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegistroEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identificador_unico: str = Field(
        min_length=1,
        max_length=255,
    )

    repositorio: str = Field(
        min_length=1,
        max_length=150,
    )

    data_hora: datetime

    usuario: str = Field(
        min_length=1,
        max_length=150,
    )

    @field_validator(
        "identificador_unico",
        "repositorio",
        "usuario",
    )
    @classmethod
    def validar_texto(cls, valor: str) -> str:
        valor = valor.strip()

        if not valor:
            raise ValueError("O campo não pode estar vazio.")

        if any(ord(caractere) < 32 for caractere in valor):
            raise ValueError("O campo contém caracteres de controle.")

        return valor

    @field_validator("data_hora")
    @classmethod
    def exigir_fuso_horario(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError(
                "data_hora deve incluir o fuso horário."
            )

        return valor


class RegistroResposta(BaseModel):
    id: int
    identificador_unico: str
    repositorio: str
    data_hora: datetime
    usuario: str
    data_hora_online: datetime

    model_config = ConfigDict(from_attributes=True)



class ChaveAPICriar(BaseModel):
    nome_sistema: str = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("nome_sistema")
    @classmethod
    def validar_nome_sistema(cls, valor: str) -> str:
        valor = valor.strip()

        if not valor:
            raise ValueError("O nome do sistema não pode estar vazio.")

        if any(ord(caractere) < 32 for caractere in valor):
            raise ValueError("O nome contém caracteres de controle.")

        return valor


class ChaveAPIResposta(BaseModel):
    id: int
    nome_sistema: str
    ativa: bool
    criada_em: datetime
    ultimo_uso_em: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ChaveAPICriada(BaseModel):
    id: int
    nome_sistema: str
    chave_api: str
    ativa: bool
    criada_em: datetime
