ALTER TABLE {schema}.seed ALTER COLUMN "GenDEr" varchar(300);

-- IRIS SQL has no multi-row VALUES, so this uses one SELECT per row joined by UNION ALL
insert into {schema}.seed (first_name, last_name, email, "GenDEr", ip_address)
select 'Annie', 'Reynolds', 'areynolds0@nifty.com', 'Amerisource Bergen', '133.30.242.211' union all
select 'Doris', 'Wood', 'dwood1@skyrock.com', 'Bliss World, LLC', '128.229.89.207' union all
select 'Andrea', 'Ray', 'aray2@google.co.jp', 'Nelco Laboratories, Inc.', '109.74.153.45' union all
select 'Frank', 'Morgan', 'fmorgan3@1688.com', 'ALK-Abello, Inc.', '252.211.209.9' union all
select 'Angela', 'Stanley', 'astanley4@google.fr', 'Gemini Pharmaceuticals, Inc. dba ONDRA Pharmaceuticals', '134.142.194.184' union all
select 'Ruby', 'Jordan', 'rjordan5@nymag.com', 'Watson Pharma, Inc.', '195.104.60.172' union all
select 'Kathleen', 'Ryan', 'kryan6@scientificamerican.com', 'SHISEIDO AMERICAS CORPORATION', '209.110.160.192' union all
select 'Margaret', 'Jacobs', 'mjacobs7@example.com', 'Cardinal Health', '72.36.52.20' union all
select 'Ernest', 'Brown', 'ebrown8@360.cn', 'West-ward Pharmaceutical Corp', '138.157.61.255' union all
select 'Elizabeth', 'Phillips', 'ephillips9@japanpost.jp', 'Cellex-C International Inc', '68.46.195.188' union all
select 'Annie', 'Ellis', 'aellisa@weather.com', 'NATURE REPUBLIC CO., LTD.', '163.128.214.142' union all
select 'Melissa', 'Olson', 'molsonb@theguardian.com', 'Nelco Laboratories, Inc.', '202.22.153.188' union all
select 'Timothy', 'Martinez', 'tmartinezc@zimbio.com', 'Lake Erie Medical & Surgical Supply DBA Quality Care Products LLC', '45.64.205.47' union all
select 'Mark', 'Nelson', 'mnelsond@bloomberg.com', '7-Eleven', '91.99.195.160' union all
select 'Kenneth', 'Hart', 'kharte@berkeley.edu', 'Preferred Pharmaceuticals, Inc.', '207.240.9.102' union all
select 'Kathryn', 'White', 'kwhitef@csmonitor.com', 'Cantrell Drug Company', '191.178.162.18' union all
select 'Mary', 'Greene', 'mgreeneg@usnews.com', 'Neutrogena Corporation', '251.226.65.64' union all
select 'Bruce', 'Peters', 'bpetersh@blogspot.com', 'Sun & Skin Care Research, LLC', '153.227.91.121' union all
select 'Albert', 'Armstrong', 'aarmstrongi@weather.com', 'Access Business Group LLC', '199.146.159.228' union all
select 'Beverly', 'Gray', 'bgrayj@spiegel.de', 'Church & Dwight Co., Inc.', '47.3.135.226' union all
select 'Catherine', 'Taylor', 'ctaylork@walmart.com', 'Matrixx Initiatives, Inc.', '82.24.129.147' union all
select 'Paula', 'Bradley', 'pbradleyl@edublogs.org', 'Nash-Finch Company', '14.145.193.163' union all
select 'Terry', 'Campbell', 'tcampbellm@artisteer.com', 'MedVantx, Inc.', '89.181.95.177' union all
select 'Bruce', 'Stevens', 'bstevensn@ucla.edu', 'Global Pharmaceuticals', '128.81.126.144' union all
select 'Ruby', 'Bishop', 'rbishopo@telegraph.co.uk', 'General Injectables & Vaccines, Inc.', '191.191.17.173' union all
select 'Denise', 'Duncan', 'dduncanp@reference.com', 'Bare Escentuals Beauty, Inc.', '150.207.3.163' union all
select 'Dennis', 'Perkins', 'dperkinsq@1und1.de', 'Altaire Pharmaceuticals Inc.', '21.150.103.133' union all
select 'Brandon', 'Ray', 'brayr@psu.edu', 'Meijer Distribution Inc', '216.53.187.191' union all
select 'Ernest', 'Graham', 'egrahams@tinyurl.com', 'BioComp Pharma, Inc.', '49.85.236.162' union all
select 'Denise', 'Matthews', 'dmatthewst@digg.com', 'Procter & Gamble Manufacturing Co.', '160.4.119.137' union all
select 'Randy', 'Alexander', 'ralexanderu@goo.gl', 'Reckitt Benckiser Pharmaceuticals Inc', '211.72.176.12' union all
select 'Aaron', 'Jackson', 'ajacksonv@gizmodo.com', 'Molton Brown LTD (UK)', '226.178.48.73' union all
select 'Wanda', 'Turner', 'wturnerw@reverbnation.com', 'American Health Packaging', '43.22.122.56' union all
select 'Stephen', 'Ferguson', 'sfergusonx@kickstarter.com', 'Amneal Pharmaceuticals of New York, LLC', '110.211.112.233' union all
select 'Jane', 'Bradley', 'jbradleyy@usgs.gov', 'Kroger Company', '186.153.255.125' union all
select 'Phillip', 'Wood', 'pwoodz@about.com', 'Unit Dose Services', '112.65.6.93' union all
select 'Jeffrey', 'Howell', 'jhowell10@symantec.com', 'Midlothian Laboratories', '232.92.208.248' union all
select 'Howard', 'Harvey', 'hharvey11@nhs.uk', 'Novartis Pharmaceuticals Corporation', '50.212.26.218' union all
select 'Benjamin', 'Johnston', 'bjohnston12@diigo.com', 'Nelco Laboratories, Inc.', '131.109.13.9' union all
select 'Ernest', 'Burke', 'eburke13@toplist.cz', 'Apotex Corp.', '151.176.178.175' union all
select 'Joe', 'Wright', 'jwright14@mapy.cz', 'MULTALER & CIE S.A.', '233.55.33.63' union all
select 'Ronald', 'Griffin', 'rgriffin15@topsy.com', 'Gavis Pharmaceuticals, LLC', '174.233.67.86' union all
select 'Susan', 'Oliver', 'soliver16@goo.gl', 'Bath & Body Works, Inc.', '104.171.43.12' union all
select 'Karen', 'Cox', 'kcox17@hp.com', 'Home Sweet Homeopathics', '225.51.182.192' union all
select 'Antonio', 'Larson', 'alarson18@gov.uk', 'Eight and Company', '243.118.98.188' union all
select 'Brandon', 'Cook', 'bcook19@mozilla.com', 'Chain Drug Consortium, LLC', '38.64.44.255' union all
select 'Gary', 'Gray', 'ggray1a@alexa.com', 'Lil'' Drug Store Products, Inc', '43.34.161.60' union all
select 'Doris', 'Harrison', 'dharrison1b@wiley.com', 'Dispensing Solutions, Inc.', '153.66.74.140' union all
select 'Clarence', 'Perry', 'cperry1c@issuu.com', 'Nelco Laboratories, Inc.', '14.72.110.59' union all
select 'Emily', 'George', 'egeorge1d@blogtalkradio.com', 'State of Florida DOH Central Pharmacy', '148.35.114.224' union all
select 'Dennis', 'Larson', 'dlarson1e@trellian.com', 'G&W Laboratories, Inc.', '134.158.117.11' union all
select 'Ashley', 'Peters', 'apeters1f@de.vu', 'Mylan Pharmaceuticals Inc.', '50.193.252.146' union all
select 'Douglas', 'Andrews', 'dandrews1g@mac.com', 'Jubilant HollisterStier LLC', '159.134.237.86' union all
select 'Craig', 'Dunn', 'cdunn1h@cornell.edu', 'Antigen Laboratories, Inc.', '227.11.100.112' union all
select 'Heather', 'Black', 'hblack1i@harvard.edu', 'Hospira, Inc.', '61.9.121.22' union all
select 'Shirley', 'Ruiz', 'sruiz1j@tmall.com', 'Hankuk Bowonbio Co., Ltd', '171.144.250.254' union all
select 'Carl', 'Martinez', 'cmartinez1k@geocities.jp', 'ALK-Abello, Inc.', '128.216.69.116' union all
select 'Stephen', 'Anderson', 'sanderson1l@odnoklassniki.ru', 'Cardinal Health', '145.154.63.186' union all
select 'Diana', 'Payne', 'dpayne1m@ftc.gov', 'Pharmaceutical Associates, Inc.', '98.9.155.136' union all
select 'Judy', 'Gonzalez', 'jgonzalez1n@walmart.com', 'SHISEIDO CO., LTD.', '73.96.109.149' union all
select 'Steve', 'Cole', 'scole1o@flickr.com', 'Walgreen Company', '251.244.20.117' union all
select 'Johnny', 'Ellis', 'jellis1p@time.com', 'Jubilant HollisterStier LLC', '188.153.76.182' union all
select 'Andrea', 'Hamilton', 'ahamilton1q@dailymail.co.uk', 'ALK-Abello, Inc.', '229.58.149.141' union all
select 'Sean', 'Kennedy', 'skennedy1r@nifty.com', 'Newton Laboratories, Inc.', '227.105.251.134' union all
select 'Sara', 'Grant', 'sgrant1s@flickr.com', 'Rubbermaid Commercial Products LLC', '96.211.162.73' union all
select 'Joan', 'Bennett', 'jbennett1t@forbes.com', 'Nelco Laboratories, Inc.', '143.27.240.163' union all
select 'Judith', 'Daniels', 'jdaniels1u@theguardian.com', 'Newton Laboratories, Inc.', '164.99.249.153' union all
select 'Irene', 'Bennett', 'ibennett1v@comsenz.com', 'Cellab Co., Ltd.', '112.104.12.122' union all
select 'Katherine', 'Perez', 'kperez1w@phpbb.com', 'Temple Industrial Welding Supply Co', '211.31.214.131' union all
select 'Jean', 'Kim', 'jkim1x@umich.edu', 'Bryant Ranch Prepack', '245.252.150.110' union all
select 'Walter', 'Hernandez', 'whernandez1y@nbcnews.com', 'Virtus Pharmaceuticals LLC', '200.201.83.21' union all
select 'Larry', 'Scott', 'lscott1z@quantcast.com', 'BIOKEY INC.', '122.141.109.98' union all
select 'Gerald', 'Palmer', 'gpalmer20@usgs.gov', 'JAFRA COSMETICS INTERNATIONAL', '60.173.159.145' union all
select 'Harry', 'Andrews', 'handrews21@alexa.com', 'NCS HealthCare of KY, Inc dba Vangard Labs', '210.64.37.91' union all
select 'Jerry', 'Morrison', 'jmorrison22@drupal.org', 'Teva Pharmaceuticals USA Inc', '83.190.174.61' union all
select 'Irene', 'Diaz', 'idiaz23@joomla.org', 'Dolgencorp, LLC', '214.16.44.235' union all
select 'Brenda', 'Hansen', 'bhansen24@wisc.edu', 'REMEDYREPACK INC.', '167.231.200.232' union all
select 'Carlos', 'Williamson', 'cwilliamson25@w3.org', 'Kroger Company', '251.202.210.204' union all
select 'David', 'Fuller', 'dfuller26@canalblog.com', 'Supervalu Inc', '175.125.205.131' union all
select 'Norma', 'Bishop', 'nbishop27@jugem.jp', 'Mylan Institutional Inc.', '208.162.25.149' union all
select 'Brenda', 'Daniels', 'bdaniels28@mediafire.com', 'Space Brands Limited', '92.235.250.138' union all
select 'Kathy', 'Reed', 'kreed29@prweb.com', 'Rugby Laboratories Inc.', '182.114.174.63' union all
select 'Anthony', 'Long', 'along2a@dropbox.com', 'Fresenius Kabi USA, LLC', '160.146.121.173' union all
select 'Craig', 'Palmer', 'cpalmer2b@desdev.cn', 'Bio-Pharm, Inc.', '135.77.134.24' union all
select 'Rachel', 'Banks', 'rbanks2c@devhub.com', 'Sam''s West Inc', '35.72.5.193' union all
select 'Kenneth', 'Peters', 'kpeters2d@ocn.ne.jp', 'International Labs, Inc.', '11.38.191.65' union all
select 'Susan', 'Clark', 'sclark2e@ed.gov', 'Shionogi Inc.', '19.243.67.80' union all
select 'Walter', 'Sullivan', 'wsullivan2f@vinaora.com', 'STAT Rx USA LLC', '154.137.170.227' union all
select 'Kathleen', 'Wood', 'kwood2g@salon.com', 'Freds Inc', '155.54.131.149' union all
select 'Phyllis', 'Henderson', 'phenderson2h@walmart.com', 'REMEDYREPACK INC.', '146.65.150.251' union all
select 'Cheryl', 'Wells', 'cwells2i@gov.uk', 'Rebel Distributors Corp', '69.127.148.31' union all
select 'Rose', 'Bradley', 'rbradley2j@un.org', 'Hi-Tech Pharmacal Co., Inc.', '150.101.165.102' union all
select 'Aaron', 'Moreno', 'amoreno2k@tinypic.com', 'Pharmacia and Upjohn Company', '50.27.226.40' union all
select 'Amy', 'Campbell', 'acampbell2l@auda.org.au', 'Chi Research, Inc.', '242.64.63.241' union all
select 'Rebecca', 'Butler', 'rbutler2m@godaddy.com', 'Cardinal Health', '40.55.159.66' union all
select 'Justin', 'Rodriguez', 'jrodriguez2n@meetup.com', 'Hikma Pharmaceutical', '118.9.132.156' union all
select 'Donald', 'Nelson', 'dnelson2o@narod.ru', 'Nature''s Way Products, Inc.', '165.174.28.134' union all
select 'Edward', 'Lawson', 'elawson2p@addtoany.com', 'Apotheca Company', '135.17.238.170' union all
select 'Paul', 'Bell', 'pbell2q@simplemachines.org', 'Washington Homeopathic Products', '235.149.137.62' union all
select 'Mark', 'Rose', 'mrose2r@google.pl', 'AMERICAN SALES COMPANY', '164.108.170.187';
