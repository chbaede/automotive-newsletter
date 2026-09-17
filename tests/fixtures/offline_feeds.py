from __future__ import annotations

SAMPLE_REUTERS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Reuters - Automotive</title>
    <link>https://www.reuters.com/business/autos-transportation/</link>
    <description>Reuters Automotive News</description>
    <item>
      <title>Volkswagen announces major European plant restructuring measures</title>
      <link>https://www.reuters.com/business/autos-transportation/vw-restructuring-europe-2026-09-17/?utm_source=rss</link>
      <description>Volkswagen Group announced comprehensive restructuring measures across its European operations to accelerate software and EV competitiveness.</description>
      <pubDate>Wed, 16 Sep 2026 14:00:00 GMT</pubDate>
      <dc:creator>Reuters</dc:creator>
    </item>
    <item>
      <title>BMW accelerates capital investment into next-generation vehicle OS</title>
      <link>https://www.reuters.com/technology/bmw-software-investment-2026-09-17/</link>
      <description>BMW announced a multi-billion euro investment into its software-defined vehicle architecture and in-house operating system platform.</description>
      <pubDate>Wed, 16 Sep 2026 11:30:00 GMT</pubDate>
      <dc:creator>Reuters</dc:creator>
    </item>
  </channel>
</rss>
"""

SAMPLE_AUTONEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Automotive News Europe</title>
    <link>https://europe.autonews.com/</link>
    <description>Automotive News Europe Feed</description>
    <item>
      <title>VW restructuring plans accelerate across German manufacturing sites</title>
      <link>https://europe.autonews.com/automakers/vw-restructuring-plans-accelerate?ref=rss</link>
      <description>Volkswagen leadership outlines aggressive cost-cutting and restructuring roadmap for European vehicle manufacturing.</description>
      <pubDate>Wed, 16 Sep 2026 15:15:00 GMT</pubDate>
    </item>
    <item>
      <title>Bosch expands zonal architecture and vehicle computer shipments</title>
      <link>https://europe.autonews.com/suppliers/bosch-zonal-architecture-hpc-shipments</link>
      <description>Tier 1 supplier Bosch reported doubling shipments of central vehicle computers and zonal ECUs for software-defined vehicle platforms.</description>
      <pubDate>Wed, 16 Sep 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_HEISE_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Heise Autos</title>
  <link href="https://www.heise.de/autos/"/>
  <updated>2026-09-16T16:00:00Z</updated>
  <entry>
    <title>Euro 7 und UNECE: Neue Sicherheits- und Abgasstandards beschlossen</title>
    <link href="https://www.heise.de/autos/artikel/euro-7-unece-standards-2026.html"/>
    <id>tag:heise.de,2026:autos-euro7-unece</id>
    <updated>2026-09-16T16:00:00Z</updated>
    <summary>Die europaeischen Regulierungsbehoerden haben den Zeitplan fuer Euro 7 und neue UNECE Cybersecurity Richtlinien praezisiert.</summary>
  </entry>
</feed>
"""

SAMPLE_BMW_OFFICIAL_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BMW Group PressClub Global</title>
    <link>https://www.press.bmwgroup.com/</link>
    <description>Official BMW Group Press Releases</description>
    <item>
      <title>BMW Group official statement on production alignment and Neue Klasse</title>
      <link>https://www.press.bmwgroup.com/global/article/detail/T0440000EN/bmw-group-production-alignment</link>
      <description>The BMW Group confirms strategic realignment of European manufacturing for Neue Klasse EV models and zonal electrical architecture.</description>
      <pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_UNECE_REGULATOR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>UNECE Sustainable Transport Division</title>
    <link>https://unece.org/transport/vehicle-regulations</link>
    <description>UNECE WP.29 Regulatory Updates</description>
    <item>
      <title>UNECE WP.29 adopts amended UN Regulation No. 155 on automotive cybersecurity</title>
      <link>https://unece.org/press/wp29-un-r155-amendment-2026</link>
      <description>The World Forum for Harmonization of Vehicle Regulations has formally adopted updated cybersecurity management system requirements.</description>
      <pubDate>Wed, 16 Sep 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
    <link>https://example.com/empty</link>
    <description>No items here</description>
  </channel>
</rss>
"""

SAMPLE_INVALID_XML = """<<<BROKEN XML NOT A VALID FEED AT ALL >>> & % ^ 12345"""

SAMPLE_MALFORMED_ARTICLES_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Malformed Feed</title>
    <link>https://example.com/malformed</link>
    <description>Feed with missing fields</description>
    <item>
      <title></title>
      <link>https://example.com/no-title</link>
      <description>Missing title entry</description>
    </item>
    <item>
      <title>Article with missing link</title>
      <link></link>
      <description>No URL present</description>
    </item>
    <item>
      <title>Article with corrupted pubDate</title>
      <link>https://example.com/bad-date</link>
      <description>Unparseable date</description>
      <pubDate>not a date</pubDate>
    </item>
  </channel>
</rss>
"""
