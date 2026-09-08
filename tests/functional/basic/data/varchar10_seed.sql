create table {schema}.seed (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	first_name VARCHAR(50),
	last_name VARCHAR(50),
	email VARCHAR(50),
	"GenDEr" VARCHAR(10),
	ip_address VARCHAR(20)
);

-- IRIS SQL has no multi-row VALUES, so this uses one SELECT per row joined by UNION ALL
insert into {schema}.seed (first_name, last_name, email, "GenDEr", ip_address)
select 'Jack', 'Hunter', 'jhunter0@pbs.org', 'Male', '59.80.20.168' union all
select 'Kathryn', 'Walker', 'kwalker1@ezinearticles.com', 'Female', '194.121.179.35' union all
select 'Gerald', 'Ryan', 'gryan2@com.com', 'Male', '11.3.212.243' union all
select 'Bonnie', 'Spencer', 'bspencer3@ameblo.jp', 'Female', '216.32.196.175' union all
select 'Harold', 'Taylor', 'htaylor4@people.com.cn', 'Male', '253.10.246.136' union all
select 'Jacqueline', 'Griffin', 'jgriffin5@t.co', 'Female', '16.13.192.220' union all
select 'Wanda', 'Arnold', 'warnold6@google.nl', 'Female', '232.116.150.64' union all
select 'Craig', 'Ortiz', 'cortiz7@sciencedaily.com', 'Male', '199.126.106.13' union all
select 'Gary', 'Day', 'gday8@nih.gov', 'Male', '35.81.68.186' union all
select 'Rose', 'Wright', 'rwright9@yahoo.co.jp', 'Female', '236.82.178.100' union all
select 'Raymond', 'Kelley', 'rkelleya@fc2.com', 'Male', '213.65.166.67' union all
select 'Gerald', 'Robinson', 'grobinsonb@disqus.com', 'Male', '72.232.194.193' union all
select 'Mildred', 'Martinez', 'mmartinezc@samsung.com', 'Female', '198.29.112.5' union all
select 'Dennis', 'Arnold', 'darnoldd@google.com', 'Male', '86.96.3.250' union all
select 'Judy', 'Gray', 'jgraye@opensource.org', 'Female', '79.218.162.245' union all
select 'Theresa', 'Garza', 'tgarzaf@epa.gov', 'Female', '21.59.100.54' union all
select 'Gerald', 'Robertson', 'grobertsong@csmonitor.com', 'Male', '131.134.82.96' union all
select 'Philip', 'Hernandez', 'phernandezh@adobe.com', 'Male', '254.196.137.72' union all
select 'Julia', 'Gonzalez', 'jgonzalezi@cam.ac.uk', 'Female', '84.240.227.174' union all
select 'Andrew', 'Davis', 'adavisj@patch.com', 'Male', '9.255.67.25' union all
select 'Kimberly', 'Harper', 'kharperk@foxnews.com', 'Female', '198.208.120.253' union all
select 'Mark', 'Martin', 'mmartinl@marketwatch.com', 'Male', '233.138.182.153' union all
select 'Cynthia', 'Ruiz', 'cruizm@google.fr', 'Female', '18.178.187.201' union all
select 'Samuel', 'Carroll', 'scarrolln@youtu.be', 'Male', '128.113.96.122' union all
select 'Jennifer', 'Larson', 'jlarsono@vinaora.com', 'Female', '98.234.85.95' union all
select 'Ashley', 'Perry', 'aperryp@rakuten.co.jp', 'Female', '247.173.114.52' union all
select 'Howard', 'Rodriguez', 'hrodriguezq@shutterfly.com', 'Male', '231.188.95.26' union all
select 'Amy', 'Brooks', 'abrooksr@theatlantic.com', 'Female', '141.199.174.118' union all
select 'Louise', 'Warren', 'lwarrens@adobe.com', 'Female', '96.105.158.28' union all
select 'Tina', 'Watson', 'twatsont@myspace.com', 'Female', '251.142.118.177' union all
select 'Janice', 'Kelley', 'jkelleyu@creativecommons.org', 'Female', '239.167.34.233' union all
select 'Terry', 'Mccoy', 'tmccoyv@bravesites.com', 'Male', '117.201.183.203' union all
select 'Jeffrey', 'Morgan', 'jmorganw@surveymonkey.com', 'Male', '78.101.78.149' union all
select 'Louis', 'Harvey', 'lharveyx@sina.com.cn', 'Male', '51.50.0.167' union all
select 'Philip', 'Miller', 'pmillery@samsung.com', 'Male', '103.255.222.110' union all
select 'Willie', 'Marshall', 'wmarshallz@ow.ly', 'Male', '149.219.91.68' union all
select 'Patrick', 'Lopez', 'plopez10@redcross.org', 'Male', '250.136.229.89' union all
select 'Adam', 'Jenkins', 'ajenkins11@harvard.edu', 'Male', '7.36.112.81' union all
select 'Benjamin', 'Cruz', 'bcruz12@linkedin.com', 'Male', '32.38.98.15' union all
select 'Ruby', 'Hawkins', 'rhawkins13@gmpg.org', 'Female', '135.171.129.255' union all
select 'Carlos', 'Barnes', 'cbarnes14@a8.net', 'Male', '240.197.85.140' union all
select 'Ruby', 'Griffin', 'rgriffin15@bravesites.com', 'Female', '19.29.135.24' union all
select 'Sean', 'Mason', 'smason16@icq.com', 'Male', '159.219.155.249' union all
select 'Anthony', 'Payne', 'apayne17@utexas.edu', 'Male', '235.168.199.218' union all
select 'Steve', 'Cruz', 'scruz18@pcworld.com', 'Male', '238.201.81.198' union all
select 'Anthony', 'Garcia', 'agarcia19@flavors.me', 'Male', '25.85.10.18' union all
select 'Doris', 'Lopez', 'dlopez1a@sphinn.com', 'Female', '245.218.51.238' union all
select 'Susan', 'Nichols', 'snichols1b@freewebs.com', 'Female', '199.99.9.61' union all
select 'Wanda', 'Ferguson', 'wferguson1c@yahoo.co.jp', 'Female', '236.241.135.21' union all
select 'Andrea', 'Pierce', 'apierce1d@google.co.uk', 'Female', '132.40.10.209' union all
select 'Lawrence', 'Phillips', 'lphillips1e@jugem.jp', 'Male', '72.226.82.87' union all
select 'Judy', 'Gilbert', 'jgilbert1f@multiply.com', 'Female', '196.250.15.142' union all
select 'Eric', 'Williams', 'ewilliams1g@joomla.org', 'Male', '222.202.73.126' union all
select 'Ralph', 'Romero', 'rromero1h@sogou.com', 'Male', '123.184.125.212' union all
select 'Jean', 'Wilson', 'jwilson1i@ocn.ne.jp', 'Female', '176.106.32.194' union all
select 'Lori', 'Reynolds', 'lreynolds1j@illinois.edu', 'Female', '114.181.203.22' union all
select 'Donald', 'Moreno', 'dmoreno1k@bbc.co.uk', 'Male', '233.249.97.60' union all
select 'Steven', 'Berry', 'sberry1l@eepurl.com', 'Male', '186.193.50.50' union all
select 'Theresa', 'Shaw', 'tshaw1m@people.com.cn', 'Female', '120.37.71.222' union all
select 'John', 'Stephens', 'jstephens1n@nationalgeographic.com', 'Male', '191.87.127.115' union all
select 'Richard', 'Jacobs', 'rjacobs1o@state.tx.us', 'Male', '66.210.83.155' union all
select 'Andrew', 'Lawson', 'alawson1p@over-blog.com', 'Male', '54.98.36.94' union all
select 'Peter', 'Morgan', 'pmorgan1q@rambler.ru', 'Male', '14.77.29.106' union all
select 'Nicole', 'Garrett', 'ngarrett1r@zimbio.com', 'Female', '21.127.74.68' union all
select 'Joshua', 'Kim', 'jkim1s@edublogs.org', 'Male', '57.255.207.41' union all
select 'Ralph', 'Roberts', 'rroberts1t@people.com.cn', 'Male', '222.143.131.109' union all
select 'George', 'Montgomery', 'gmontgomery1u@smugmug.com', 'Male', '76.75.111.77' union all
select 'Gerald', 'Alvarez', 'galvarez1v@flavors.me', 'Male', '58.157.186.194' union all
select 'Donald', 'Olson', 'dolson1w@whitehouse.gov', 'Male', '69.65.74.135' union all
select 'Carlos', 'Morgan', 'cmorgan1x@pbs.org', 'Male', '96.20.140.87' union all
select 'Aaron', 'Stanley', 'astanley1y@webnode.com', 'Male', '163.119.217.44' union all
select 'Virginia', 'Long', 'vlong1z@spiegel.de', 'Female', '204.150.194.182' union all
select 'Robert', 'Berry', 'rberry20@tripadvisor.com', 'Male', '104.19.48.241' union all
select 'Antonio', 'Brooks', 'abrooks21@unesco.org', 'Male', '210.31.7.24' union all
select 'Ruby', 'Garcia', 'rgarcia22@ovh.net', 'Female', '233.218.162.214' union all
select 'Jack', 'Hanson', 'jhanson23@blogtalkradio.com', 'Male', '31.55.46.199' union all
select 'Kathryn', 'Nelson', 'knelson24@walmart.com', 'Female', '14.189.146.41' union all
select 'Jason', 'Reed', 'jreed25@printfriendly.com', 'Male', '141.189.89.255' union all
select 'George', 'Coleman', 'gcoleman26@people.com.cn', 'Male', '81.189.221.144' union all
select 'Rose', 'King', 'rking27@ucoz.com', 'Female', '212.123.168.231' union all
select 'Johnny', 'Holmes', 'jholmes28@boston.com', 'Male', '177.3.93.188' union all
select 'Katherine', 'Gilbert', 'kgilbert29@altervista.org', 'Female', '199.215.169.61' union all
select 'Joshua', 'Thomas', 'jthomas2a@ustream.tv', 'Male', '0.8.205.30' union all
select 'Julie', 'Perry', 'jperry2b@opensource.org', 'Female', '60.116.114.192' union all
select 'Richard', 'Perry', 'rperry2c@oracle.com', 'Male', '181.125.70.232' union all
select 'Kenneth', 'Ruiz', 'kruiz2d@wikimedia.org', 'Male', '189.105.137.109' union all
select 'Jose', 'Morgan', 'jmorgan2e@webnode.com', 'Male', '101.134.215.156' union all
select 'Donald', 'Campbell', 'dcampbell2f@goo.ne.jp', 'Male', '102.120.215.84' union all
select 'Debra', 'Collins', 'dcollins2g@uol.com.br', 'Female', '90.13.153.235' union all
select 'Jesse', 'Johnson', 'jjohnson2h@stumbleupon.com', 'Male', '225.178.125.53' union all
select 'Elizabeth', 'Stone', 'estone2i@histats.com', 'Female', '123.184.126.221' union all
select 'Angela', 'Rogers', 'arogers2j@goodreads.com', 'Female', '98.104.132.187' union all
select 'Emily', 'Dixon', 'edixon2k@mlb.com', 'Female', '39.190.75.57' union all
select 'Albert', 'Scott', 'ascott2l@tinypic.com', 'Male', '40.209.13.189' union all
select 'Barbara', 'Peterson', 'bpeterson2m@ow.ly', 'Female', '75.249.136.180' union all
select 'Adam', 'Greene', 'agreene2n@fastcompany.com', 'Male', '184.173.109.144' union all
select 'Earl', 'Sanders', 'esanders2o@hc360.com', 'Male', '247.34.90.117' union all
select 'Angela', 'Brooks', 'abrooks2p@mtv.com', 'Female', '10.63.249.126' union all
select 'Harold', 'Foster', 'hfoster2q@privacy.gov.au', 'Male', '139.214.40.244' union all
select 'Carl', 'Meyer', 'cmeyer2r@disqus.com', 'Male', '204.117.7.88';
