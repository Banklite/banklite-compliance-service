-- Datos de ejemplo de compliance-service. Ejecutar despues de schema.sql.
INSERT INTO reporte_regulatorio (id_reporte, tipo_reporte, periodo, estado, contenido) VALUES
 ('a1000000-0000-0000-0000-000000000001','ROS','2026-10','borrador','Reporte de ejemplo')
ON CONFLICT DO NOTHING;
INSERT INTO transaccion_monitoreada (id_transferencia, id_cuenta_origen, monto, fecha_transaccion, marcada) VALUES
 ('50000000-0000-0000-0000-000000000001','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1',50000,now(),'no')
ON CONFLICT DO NOTHING;
INSERT INTO transaccion_sospechosa (id_sospecha, id_transferencia, id_cuenta_origen, id_usuario, motivo, nivel_riesgo, monto, id_reporte, estado) VALUES
 ('a2000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000009','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','Ejemplo: monto sobre el umbral AML','medio',12000000,'a1000000-0000-0000-0000-000000000001','pendiente')
ON CONFLICT DO NOTHING;
INSERT INTO auditoria (id_auditoria, id_sospecha, auditor, resultado, notas) VALUES
 ('a3000000-0000-0000-0000-000000000001','a2000000-0000-0000-0000-000000000001','Oficial de cumplimiento','sospechosa','Pendiente de revision')
ON CONFLICT DO NOTHING;
