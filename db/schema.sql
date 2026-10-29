-- Esquema de compliance-service (PostgreSQL). Generado a partir de los modelos SQLAlchemy.
-- Tambien se crea solo al arrancar el servicio (Base.metadata.create_all).

CREATE TABLE reporte_regulatorio (
	id_reporte UUID NOT NULL, 
	tipo_reporte VARCHAR(50) NOT NULL, 
	periodo VARCHAR(30) NOT NULL, 
	fecha_generacion TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	estado VARCHAR(20) NOT NULL, 
	contenido TEXT, 
	generado_por UUID, 
	PRIMARY KEY (id_reporte), 
	CONSTRAINT chk_reporte_estado CHECK (estado IN ('borrador', 'enviado', 'aceptado', 'rechazado'))
);

CREATE TABLE transaccion_monitoreada (
	id_transferencia UUID NOT NULL, 
	id_cuenta_origen UUID NOT NULL, 
	monto NUMERIC(14, 2) NOT NULL, 
	fecha_transaccion TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	marcada VARCHAR(5) NOT NULL, 
	PRIMARY KEY (id_transferencia)
);
CREATE INDEX idx_monitoreada_fecha ON transaccion_monitoreada (fecha_transaccion);

CREATE TABLE transaccion_sospechosa (
	id_sospecha UUID NOT NULL, 
	id_transferencia UUID NOT NULL, 
	id_cuenta_origen UUID NOT NULL, 
	id_usuario UUID NOT NULL, 
	motivo VARCHAR(255) NOT NULL, 
	nivel_riesgo VARCHAR(20) NOT NULL, 
	monto NUMERIC(14, 2), 
	fecha_deteccion TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	id_reporte UUID, 
	estado VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id_sospecha), 
	CONSTRAINT chk_sospechosa_nivel_riesgo CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto', 'critico')), 
	CONSTRAINT chk_sospechosa_estado CHECK (estado IN ('pendiente', 'investigando', 'descartada', 'confirmada', 'reportada')), 
	FOREIGN KEY(id_reporte) REFERENCES reporte_regulatorio (id_reporte)
);
CREATE INDEX idx_sospechosa_transferencia ON transaccion_sospechosa (id_transferencia);
CREATE INDEX idx_sospechosa_usuario ON transaccion_sospechosa (id_usuario);

CREATE TABLE auditoria (
	id_auditoria UUID NOT NULL, 
	id_sospecha UUID NOT NULL, 
	auditor VARCHAR(150), 
	resultado VARCHAR(30) NOT NULL, 
	notas TEXT, 
	fecha_auditoria TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id_auditoria), 
	CONSTRAINT chk_auditoria_resultado CHECK (resultado IN ('limpia', 'sospechosa', 'confirmada_fraude')), 
	FOREIGN KEY(id_sospecha) REFERENCES transaccion_sospechosa (id_sospecha)
);
CREATE INDEX idx_auditoria_sospecha ON auditoria (id_sospecha);
