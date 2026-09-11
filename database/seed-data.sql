-- Seed data: SeguraPro Corretora de Seguros

INSERT INTO departments (name, description) VALUES
('Seguros Pessoais', 'Auto, vida, residencial para pessoa física'),
('Seguros Empresariais', 'Patrimonial, responsabilidade civil, frota'),
('Saúde e Odonto', 'Planos de saúde e odontológicos coletivos'),
('Comercial', 'Prospecção e novos negócios'),
('Sinistros', 'Regulação e acompanhamento de sinistros');

INSERT INTO brokers (department_id, registration_number, full_name, email, phone, hire_date, status, commission_rate) VALUES
(1, 'SUSEP-10201', 'Ana Carolina Mendes', 'ana.mendes@segurapro.com.br', '(85)99901-1001', '2019-03-15', 'active', 12.00),
(1, 'SUSEP-10202', 'Bruno Ferreira Lima', 'bruno.lima@segurapro.com.br', '(85)99901-1002', '2020-07-01', 'active', 10.00),
(2, 'SUSEP-10203', 'Carla Rodrigues Silva', 'carla.silva@segurapro.com.br', '(85)99901-1003', '2018-01-10', 'active', 15.00),
(2, 'SUSEP-10204', 'Daniel Souza Costa', 'daniel.costa@segurapro.com.br', '(85)99901-1004', '2021-05-20', 'active', 10.00),
(3, 'SUSEP-10205', 'Eduardo Alves Pinto', 'eduardo.pinto@segurapro.com.br', '(85)99901-1005', '2017-11-01', 'active', 8.00),
(3, 'SUSEP-10206', 'Fernanda Oliveira Ramos', 'fernanda.ramos@segurapro.com.br', '(85)99901-1006', '2022-02-14', 'active', 8.00),
(4, 'SUSEP-10207', 'Gabriel Nascimento Reis', 'gabriel.reis@segurapro.com.br', '(85)99901-1007', '2020-09-01', 'active', 11.00),
(1, 'SUSEP-10208', 'Helena Costa Barros', 'helena.barros@segurapro.com.br', '(85)99901-1008', '2023-01-15', 'active', 10.00),
(2, 'SUSEP-10209', 'Igor Martins Duarte', 'igor.duarte@segurapro.com.br', '(85)99901-1009', '2019-06-10', 'inactive', 12.00),
(4, 'SUSEP-10210', 'Juliana Pereira Lopes', 'juliana.lopes@segurapro.com.br', '(85)99901-1010', '2021-08-01', 'on_leave', 10.00);

INSERT INTO insurers (name, cnpj, susep_code, website, contact_email, contact_phone, status) VALUES
('Porto Seguro S.A.', '61.198.164/0001-60', '0Portal', 'https://www.portoseguro.com.br', 'corretor@portoseguro.com.br', '(11)3366-3000', 'active'),
('SulAmérica Seguros', '33.000.118/0001-79', '0785', 'https://www.sulamerica.com.br', 'comercial@sulamerica.com.br', '(21)2122-7000', 'active'),
('Bradesco Seguros', '33.055.146/0001-51', '0535', 'https://www.bradescoseguros.com.br', 'seguro@bradesco.com.br', '(11)4002-0022', 'active'),
('Tokio Marine', '33.164.021/0001-00', '0524', 'https://www.tokiomarine.com.br', 'comercial@tokiomarine.com.br', '(11)3054-7100', 'active'),
('HDI Seguros', '29.980.158/0001-57', '0759', 'https://www.hdi.com.br', 'corretor@hdi.com.br', '(11)3457-2929', 'active'),
('Allianz Seguros', '61.573.796/0001-66', '0515', 'https://www.allianz.com.br', 'comercial@allianz.com.br', '(11)3370-2200', 'active'),
('Liberty Seguros', '61.550.141/0001-72', '0588', 'https://www.libertyseguros.com.br', 'corretor@liberty.com.br', '(11)3416-6100', 'active'),
('Mapfre Seguros', '61.074.175/0001-38', '0510', 'https://www.mapfre.com.br', 'comercial@mapfre.com.br', '(11)4004-0101', 'active'),
('Zurich Seguros', '01.585.474/0001-82', '0748', 'https://www.zurich.com.br', 'corretor@zurich.com.br', '(11)3272-1300', 'active'),
('Itaú Seguros', '33.065.699/0001-27', '0553', 'https://www.itauseguros.com.br', 'seguro@itau.com.br', '(11)4004-4822', 'active');

INSERT INTO insurance_branches (code, name, description, susep_group) VALUES
('0531', 'Automóvel - Casco', 'Cobertura de danos ao veículo do segurado', 'Automóvel'),
('0553', 'Automóvel - RCF-V', 'Responsabilidade civil facultativa de veículos', 'Automóvel'),
('0993', 'Vida Individual', 'Seguro de vida individual com coberturas por morte e invalidez', 'Pessoas'),
('0994', 'Vida em Grupo', 'Seguro de vida coletivo para empresas', 'Pessoas'),
('1130', 'Residencial', 'Seguro para imóveis residenciais', 'Patrimonial'),
('1131', 'Empresarial', 'Seguro patrimonial para empresas e comércios', 'Patrimonial'),
('1381', 'Saúde Coletivo', 'Plano de saúde coletivo empresarial', 'Saúde'),
('1608', 'Resp. Civil Geral', 'Responsabilidade civil de operações', 'Responsabilidade'),
('0171', 'Riscos de Engenharia', 'Cobertura para obras e instalações', 'Patrimonial'),
('0196', 'Transportes', 'Seguro de cargas e transportes', 'Transportes');

INSERT INTO products (insurer_id, branch_id, name, description, min_premium, status) VALUES
(1, 1, 'Porto Auto Essencial', 'Seguro auto com coberturas básicas', 1200.00, 'active'),
(1, 1, 'Porto Auto Completo', 'Seguro auto com assistência 24h e carro reserva', 2400.00, 'active'),
(1, 5, 'Porto Residência', 'Seguro residencial com incêndio, roubo e RC', 350.00, 'active'),
(1, 3, 'Porto Vida Mais', 'Vida individual com morte e IPA', 80.00, 'active'),
(2, 7, 'SulAmérica Saúde PME', 'Plano saúde para 3-29 vidas', 450.00, 'active'),
(2, 3, 'SulAmérica Vida', 'Vida individual com assistência funeral', 65.00, 'active'),
(2, 1, 'SulAmérica Auto', 'Auto com cobertura nacional', 1800.00, 'active'),
(3, 1, 'Bradesco Auto Fácil', 'Seguro auto com perfil simplificado', 1500.00, 'active'),
(3, 4, 'Bradesco Vida Empresa', 'Vida em grupo para PMEs', 35.00, 'active'),
(3, 6, 'Bradesco Empresarial', 'Seguro patrimonial empresarial completo', 800.00, 'active'),
(4, 1, 'Tokio Auto Premium', 'Auto top com guincho ilimitado', 2800.00, 'active'),
(4, 5, 'Tokio Residencial Plus', 'Residencial com RC e danos elétricos', 280.00, 'active'),
(5, 1, 'HDI Auto Leve', 'Auto econômico para veículos até 3 anos', 1100.00, 'active'),
(5, 6, 'HDI Empresarial', 'Patrimonial para comércios e escritórios', 600.00, 'active'),
(6, 8, 'Allianz RC Profissional', 'Responsabilidade civil para profissionais liberais', 500.00, 'active'),
(6, 1, 'Allianz Auto', 'Auto com desconto por telemetria', 1600.00, 'active'),
(7, 1, 'Liberty Auto', 'Auto com assistência completa', 1700.00, 'active'),
(7, 5, 'Liberty Residencial', 'Residencial básico', 200.00, 'active'),
(8, 9, 'Mapfre Risco Engenharia', 'Cobertura para obras civis e montagens', 3500.00, 'active'),
(8, 1, 'Mapfre Auto', 'Auto com oficina referenciada', 1400.00, 'active'),
(9, 10, 'Zurich Transportes', 'Seguro de carga nacional e internacional', 1200.00, 'active'),
(9, 6, 'Zurich Empresarial Max', 'Patrimonial empresarial com lucros cessantes', 1500.00, 'active'),
(10, 3, 'Itaú Vida Simples', 'Vida individual simplificado', 45.00, 'active'),
(10, 4, 'Itaú Vida Grupo', 'Vida em grupo coletivo', 28.00, 'active');

INSERT INTO clients (client_type, document_number, full_name, trade_name, email, phone, birth_date, address_street, address_number, address_neighborhood, address_city, address_state, address_zip, broker_id, status) VALUES
('PF','123.456.789-01','Maria José da Silva',NULL,'maria.silva@email.com','(85)99801-0001','1985-03-12','Rua das Flores','120','Aldeota','Fortaleza','CE','60150-000',1,'active'),
('PF','234.567.890-12','João Pedro Almeida',NULL,'joao.almeida@email.com','(85)99801-0002','1978-07-25','Av. Beira Mar','450','Meireles','Fortaleza','CE','60165-121',1,'active'),
('PJ','12.345.678/0001-90','Comércio Estrela do Norte Ltda','Estrela do Norte','contato@estreladonorte.com.br','(85)3201-0001','2010-05-10','Rua Barão de Aracati','800','Centro','Fortaleza','CE','60115-080',3,'active'),
('PF','345.678.901-23','Ana Paula Santos Rodrigues',NULL,'ana.rodrigues@email.com','(85)99801-0003','1990-11-30','Rua Tibúrcio Cavalcante','55','Dionísio Torres','Fortaleza','CE','60125-100',2,'active'),
('PJ','23.456.789/0001-01','Tech Solutions Informática S.A.','TechSol','financeiro@techsol.com.br','(85)3201-0002','2015-08-20','Av. Santos Dumont','1500','Papicu','Fortaleza','CE','60150-160',3,'active'),
('PF','456.789.012-34','Carlos Eduardo Lima Neto',NULL,'carlos.neto@email.com','(85)99801-0004','1972-01-18','Rua Frederico Borges','230','Varjota','Fortaleza','CE','60175-060',2,'active'),
('PF','567.890.123-45','Francisca Moreira Costa',NULL,'francisca.costa@email.com','(85)99801-0005','1965-09-05','Av. Desembargador Moreira','1200','Aldeota','Fortaleza','CE','60170-002',1,'active'),
('PJ','34.567.890/0001-12','Restaurante Sabor Cearense Ltda','Sabor Cearense','adm@saborcearense.com.br','(85)3201-0003','2012-03-01','Rua Ana Bilhar','300','Meireles','Fortaleza','CE','60160-110',4,'active'),
('PF','678.901.234-56','Pedro Henrique de Sousa',NULL,'pedro.sousa@email.com','(85)99801-0006','1995-04-22','Rua Canuto de Aguiar','88','Meireles','Fortaleza','CE','60160-120',7,'active'),
('PF','789.012.345-67','Lucia Helena Barbosa',NULL,'lucia.barbosa@email.com','(85)99801-0007','1980-12-14','Av. Abolição','2100','Mucuripe','Fortaleza','CE','60165-070',1,'active'),
('PJ','45.678.901/0001-23','Construtora Fortaleza Engenharia Ltda','Fortaleza Eng.','eng@forteng.com.br','(85)3201-0004','2008-11-15','Rua Leonardo Mota','750','Dionísio Torres','Fortaleza','CE','60170-041',3,'active'),
('PF','890.123.456-78','Roberto Carlos Nascimento',NULL,'roberto.nasc@email.com','(85)99801-0008','1988-06-30','Rua Pereira Valente','140','Varjota','Fortaleza','CE','60160-250',8,'active'),
('PF','901.234.567-89','Antônia Maria Vieira',NULL,'antonia.vieira@email.com','(85)99801-0009','1970-02-28','Av. Dom Luís','500','Aldeota','Fortaleza','CE','60160-230',2,'active'),
('PJ','56.789.012/0001-34','Clínica Vida e Saúde S.S.','Vida e Saúde','clinica@vidaesaude.com.br','(85)3201-0005','2005-06-01','Rua Nunes Valente','400','Aldeota','Fortaleza','CE','60135-270',5,'active'),
('PF','012.345.678-90','Fernando Augusto Moura',NULL,'fernando.moura@email.com','(85)99801-0010','1992-08-17','Rua Torres Câmara','60','Aldeota','Fortaleza','CE','60150-060',7,'active'),
('PJ','67.890.123/0001-45','Transportadora Jangadeiro Ltda','Jangadeiro Log','contato@jangadeiro.com.br','(85)3201-0006','2014-01-20','BR-116 km 12','S/N','Messejana','Fortaleza','CE','60871-100',4,'active'),
('PF','111.222.333-44','Raquel de Oliveira Pires',NULL,'raquel.pires@email.com','(85)99801-0011','1983-10-10','Rua Costa Barros','320','Centro','Fortaleza','CE','60060-460',8,'active'),
('PF','222.333.444-55','Marcos Antônio da Rocha',NULL,'marcos.rocha@email.com','(85)99801-0012','1975-05-05','Av. Pontes Vieira','1800','São João do Tauape','Fortaleza','CE','60130-241',2,'active'),
('PJ','78.901.234/0001-56','Padaria Pão de Mel Ltda','Pão de Mel','paodemel@email.com','(85)3201-0007','2018-04-15','Rua Padre Valdevino','200','Centro','Fortaleza','CE','60135-040',4,'active'),
('PF','333.444.555-66','Sandra Maria Bezerra',NULL,'sandra.bezerra@email.com','(85)99801-0013','1968-07-20','Rua Nogueira Acioli','450','Centro','Fortaleza','CE','60110-140',1,'active');

INSERT INTO policies (policy_number, client_id, product_id, broker_id, start_date, end_date, premium_amount, insured_amount, payment_method, installments, status, issued_at) VALUES
('APL-2024-00001',1,1,1,'2024-01-15','2025-01-15',2850.00,85000.00,'boleto',4,'expired','2024-01-10'),
('APL-2024-00002',2,2,1,'2024-03-01','2025-03-01',4200.00,120000.00,'cartao_credito',6,'active','2024-02-25'),
('APL-2024-00003',3,10,3,'2024-02-10','2025-02-10',3500.00,500000.00,'boleto',4,'active','2024-02-05'),
('APL-2024-00004',4,1,2,'2024-04-01','2025-04-01',1800.00,65000.00,'pix',1,'active','2024-03-28'),
('APL-2024-00005',5,14,3,'2024-01-20','2025-01-20',2200.00,350000.00,'boleto',4,'expired','2024-01-15'),
('APL-2024-00006',6,4,2,'2024-05-01','2025-05-01',480.00,200000.00,'debito_conta',12,'active','2024-04-25'),
('APL-2024-00007',7,3,1,'2024-06-15','2025-06-15',580.00,150000.00,'boleto',1,'active','2024-06-10'),
('APL-2024-00008',8,14,4,'2024-03-10','2025-03-10',1800.00,280000.00,'boleto',4,'active','2024-03-05'),
('APL-2024-00009',9,11,7,'2024-07-01','2025-07-01',5200.00,180000.00,'cartao_credito',6,'active','2024-06-25'),
('APL-2024-00010',10,1,1,'2024-08-01','2025-08-01',2100.00,72000.00,'pix',1,'active','2024-07-28'),
('APL-2024-00011',11,19,3,'2024-04-15','2025-04-15',8500.00,2000000.00,'boleto',4,'active','2024-04-10'),
('APL-2024-00012',12,16,8,'2024-09-01','2025-09-01',3200.00,95000.00,'cartao_credito',6,'active','2024-08-28'),
('APL-2024-00013',13,6,2,'2024-02-01','2025-02-01',780.00,300000.00,'boleto',12,'active','2024-01-25'),
('APL-2024-00014',14,5,5,'2024-05-15','2025-05-15',12500.00,500000.00,'boleto',12,'active','2024-05-10'),
('APL-2024-00015',15,13,7,'2024-10-01','2025-10-01',1650.00,55000.00,'debito_conta',4,'active','2024-09-28'),
('APL-2025-00001',1,2,1,'2025-01-20','2026-01-20',3100.00,90000.00,'boleto',4,'active','2025-01-15'),
('APL-2025-00002',3,10,3,'2025-02-15','2026-02-15',3800.00,550000.00,'boleto',4,'active','2025-02-10'),
('APL-2025-00003',9,3,7,'2025-03-01','2026-03-01',650.00,180000.00,'pix',1,'active','2025-02-25'),
('APL-2025-00004',14,9,5,'2025-04-01','2026-04-01',8400.00,250000.00,'boleto',12,'active','2025-03-28'),
('APL-2025-00005',11,19,3,'2025-05-01','2026-05-01',9200.00,2200000.00,'boleto',4,'active','2025-04-28');

INSERT INTO policy_coverages (policy_id, coverage_name, coverage_amount, deductible, is_main) VALUES
(1,'Casco - Colisão',85000.00,2500.00,true),
(1,'Casco - Incêndio e Roubo',85000.00,0.00,false),
(1,'RCF-V Danos Materiais',100000.00,0.00,false),
(2,'Casco - Compreensiva',120000.00,3200.00,true),
(2,'RCF-V Danos Materiais',150000.00,0.00,false),
(2,'RCF-V Danos Corporais',200000.00,0.00,false),
(2,'Carro Reserva 15 dias',0.00,0.00,false),
(3,'Incêndio',500000.00,5000.00,true),
(3,'Vendaval e Granizo',300000.00,3000.00,false),
(3,'Roubo de Bens',150000.00,2000.00,false),
(4,'Casco - Colisão',65000.00,1800.00,true),
(4,'RCF-V Danos Materiais',80000.00,0.00,false),
(6,'Morte Acidental',200000.00,0.00,true),
(6,'Invalidez Permanente Total',200000.00,0.00,false),
(7,'Incêndio',150000.00,1500.00,true),
(7,'Roubo',80000.00,800.00,false),
(7,'Danos Elétricos',30000.00,300.00,false),
(9,'Casco Compreensiva',180000.00,5500.00,true),
(9,'RCF-V Materiais e Corporais',300000.00,0.00,false),
(14,'Consultas e Exames',0.00,0.00,true),
(14,'Internação',0.00,0.00,false);

INSERT INTO claims (claim_number, policy_id, occurrence_date, notification_date, description, estimated_loss, approved_amount, status, denial_reason, closed_at) VALUES
('SIN-2024-00001',1,'2024-06-15','2024-06-16','Colisão traseira no cruzamento da Av. Santos Dumont',12000.00,10500.00,'paid',NULL,'2024-08-20 14:30:00'),
('SIN-2024-00002',2,'2024-08-22','2024-08-23','Furto do veículo no Shopping Iguatemi',120000.00,115000.00,'paid',NULL,'2024-11-15 10:00:00'),
('SIN-2024-00003',3,'2024-07-10','2024-07-11','Curto-circuito causou incêndio no estoque',45000.00,38000.00,'paid',NULL,'2024-09-30 16:00:00'),
('SIN-2024-00004',7,'2024-09-05','2024-09-06','Vazamento danificou forro e móveis',8500.00,7200.00,'approved',NULL,NULL),
('SIN-2024-00005',4,'2024-10-12','2024-10-13','Alagamento danificou sistema elétrico do veículo',15000.00,NULL,'in_analysis',NULL,NULL),
('SIN-2024-00006',9,'2024-11-20','2024-11-21','Colisão frontal na CE-040',35000.00,NULL,'in_analysis',NULL,NULL),
('SIN-2024-00007',6,'2024-08-01','2024-08-15','Falecimento do segurado por causas naturais',200000.00,200000.00,'paid',NULL,'2024-10-05 09:00:00'),
('SIN-2024-00008',10,'2024-12-01','2024-12-02','Roubo do veículo na Av. Washington Soares',72000.00,NULL,'open',NULL,NULL),
('SIN-2025-00001',16,'2025-03-15','2025-03-16','Veículo atingido por árvore durante tempestade',22000.00,18500.00,'approved',NULL,NULL),
('SIN-2025-00002',17,'2025-05-10','2025-05-12','Incêndio parcial no galpão da empresa',280000.00,NULL,'in_analysis',NULL,NULL),
('SIN-2024-00009',12,'2024-10-20','2024-10-22','Tentativa de furto - danos na porta',3500.00,0.00,'denied','Danos não cobertos pela apólice','2024-12-10 15:00:00');

INSERT INTO commissions (policy_id, broker_id, commission_rate, commission_amount, status, due_date, paid_at) VALUES
(1,1,12.00,342.00,'paid','2024-02-15','2024-02-20 10:00:00'),
(2,1,12.00,504.00,'paid','2024-04-01','2024-04-05 10:00:00'),
(3,3,15.00,525.00,'paid','2024-03-10','2024-03-15 10:00:00'),
(4,2,10.00,180.00,'paid','2024-05-01','2024-05-05 10:00:00'),
(5,3,15.00,330.00,'paid','2024-02-20','2024-02-25 10:00:00'),
(9,7,11.00,572.00,'paid','2024-08-01','2024-08-05 10:00:00'),
(11,3,15.00,1275.00,'paid','2024-05-15','2024-05-20 10:00:00'),
(14,5,8.00,1000.00,'paid','2024-06-15','2024-06-20 10:00:00'),
(16,1,12.00,372.00,'pending','2025-02-20',NULL),
(17,3,15.00,570.00,'pending','2025-03-15',NULL),
(20,3,15.00,1380.00,'pending','2025-06-01',NULL);

INSERT INTO payments (policy_id, installment_number, due_date, amount, paid_amount, paid_at, status, payment_method) VALUES
(1,1,'2024-01-20',712.50,712.50,'2024-01-18 09:00:00','paid','boleto'),
(1,2,'2024-02-20',712.50,712.50,'2024-02-19 14:00:00','paid','boleto'),
(1,3,'2024-03-20',712.50,712.50,'2024-03-20 11:00:00','paid','boleto'),
(1,4,'2024-04-20',712.50,712.50,'2024-04-22 10:00:00','paid','boleto'),
(2,1,'2024-03-05',700.00,700.00,'2024-03-04 08:00:00','paid','cartao_credito'),
(2,2,'2024-04-05',700.00,700.00,'2024-04-05 08:00:00','paid','cartao_credito'),
(2,3,'2024-05-05',700.00,700.00,'2024-05-05 08:00:00','paid','cartao_credito'),
(2,4,'2024-06-05',700.00,700.00,'2024-06-05 08:00:00','paid','cartao_credito'),
(2,5,'2024-07-05',700.00,700.00,'2024-07-04 15:00:00','paid','cartao_credito'),
(2,6,'2024-08-05',700.00,700.00,'2024-08-05 08:00:00','paid','cartao_credito'),
(16,1,'2025-01-25',775.00,775.00,'2025-01-24 09:00:00','paid','boleto'),
(16,2,'2025-02-25',775.00,775.00,'2025-02-25 14:00:00','paid','boleto'),
(16,3,'2025-03-25',775.00,NULL,NULL,'overdue',NULL),
(16,4,'2025-04-25',775.00,NULL,NULL,'pending',NULL);

INSERT INTO quotes (quote_number, client_id, broker_id, branch_id, requested_at, valid_until, status, notes) VALUES
('COT-2025-00001',15,7,1,'2025-06-01 10:00:00','2025-06-15','accepted','Cliente quer trocar de seguradora'),
('COT-2025-00002',12,8,1,'2025-06-10 14:00:00','2025-06-24','sent','Primeiro seguro, veículo 0km'),
('COT-2025-00003',19,4,6,'2025-06-15 09:00:00','2025-06-29','pending','Seguro empresarial para nova filial'),
('COT-2025-00004',14,5,7,'2025-07-05 16:00:00','2025-07-19','rejected','Cliente achou valores altos');

INSERT INTO quote_items (quote_id, insurer_id, product_id, premium_amount, insured_amount, is_selected) VALUES
(1,1,1,1500.00,55000.00,false),
(1,5,13,1350.00,55000.00,true),
(1,8,20,1480.00,55000.00,false),
(2,1,2,4100.00,105000.00,false),
(2,4,11,4800.00,105000.00,false),
(2,6,16,3900.00,105000.00,false),
(3,5,14,1400.00,200000.00,false),
(3,3,10,1250.00,200000.00,false),
(4,2,5,15000.00,600000.00,false),
(4,3,9,12800.00,600000.00,false);

INSERT INTO endorsements (policy_id, endorsement_number, type, description, premium_difference, effective_date) VALUES
(2,'END-2024-00001','modification','Inclusão de carro reserva por 30 dias',280.00,'2024-05-01'),
(3,'END-2024-00002','inclusion','Inclusão de cobertura de vendaval',450.00,'2024-06-01'),
(9,'END-2024-00003','modification','Alteração de franquia para R$ 4.000',-350.00,'2024-09-01'),
(14,'END-2025-00001','inclusion','Inclusão de 5 novas vidas no plano',2250.00,'2025-03-01');

INSERT INTO claim_documents (claim_id, document_type, file_name) VALUES
(1,'boletim_ocorrencia','BO_2024_06_15_colisao.pdf'),
(1,'foto','foto_dano_traseira_01.jpg'),
(1,'orcamento','orcamento_funilaria.pdf'),
(2,'boletim_ocorrencia','BO_2024_08_22_furto.pdf'),
(2,'foto','foto_local_estacionamento.jpg'),
(3,'laudo_pericial','laudo_incendio_eletrico.pdf'),
(3,'nota_fiscal','NF_equipamentos_danificados.pdf'),
(7,'outros','certidao_obito.pdf'),
(7,'outros','documentos_beneficiarios.pdf'),
(8,'boletim_ocorrencia','BO_2024_12_01_roubo.pdf');

-- Criar usuário read-only para o QueryMind
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'segurapro_readonly') THEN
    CREATE USER segurapro_readonly WITH PASSWORD 'segurapro_dev';
  END IF;
END $$;
GRANT CONNECT ON DATABASE segurapro TO segurapro_readonly;
GRANT USAGE ON SCHEMA public TO segurapro_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO segurapro_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO segurapro_readonly;
