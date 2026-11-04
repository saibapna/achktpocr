from typing import Literal

from pydantic import BaseModel, Field


class FieldResult(BaseModel):
    value: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str | None = None
    validation: Literal["passed", "warning", "failed", "not_checked"] = "not_checked"
    warnings: list[str] = Field(default_factory=list)


class KTPFields(BaseModel):
    nik: FieldResult = Field(default_factory=FieldResult)
    nama: FieldResult = Field(default_factory=FieldResult)
    tempat_lahir: FieldResult = Field(default_factory=FieldResult)
    tanggal_lahir: FieldResult = Field(default_factory=FieldResult)
    jenis_kelamin: FieldResult = Field(default_factory=FieldResult)
    gol_darah: FieldResult = Field(default_factory=FieldResult)
    alamat: FieldResult = Field(default_factory=FieldResult)
    rt_rw: FieldResult = Field(default_factory=FieldResult)
    kel_desa: FieldResult = Field(default_factory=FieldResult)
    kecamatan: FieldResult = Field(default_factory=FieldResult)
    agama: FieldResult = Field(default_factory=FieldResult)
    status_perkawinan: FieldResult = Field(default_factory=FieldResult)
    pekerjaan: FieldResult = Field(default_factory=FieldResult)
    kewarganegaraan: FieldResult = Field(default_factory=FieldResult)
    berlaku_hingga: FieldResult = Field(default_factory=FieldResult)
    provinsi: FieldResult = Field(default_factory=FieldResult)
    kabupaten_kota: FieldResult = Field(default_factory=FieldResult)


class OCRResponse(BaseModel):
    request_id: str
    status: Literal["success", "partial", "failed"]
    document_type: Literal["ktp_el", "unknown"]
    data: dict[str, str | None]
    fields: KTPFields
    warnings: list[str] = Field(default_factory=list)
    processing: dict[str, float | int] = Field(default_factory=dict)
    model_version: str | None = None
