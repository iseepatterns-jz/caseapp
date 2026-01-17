"""
Forensic analysis service for email and text message analysis
"""

import asyncio
import sqlite3
import os
import hashlib
import json
import re
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
import pandas as pd
import numpy as np
from email import message_from_string
from email.header import decode_header
import mailbox
import plistlib
import biplist

# NLP and analysis libraries
import spacy
from textblob import TextBlob
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation

from core.database import AsyncSessionLocal
from models.forensic_analysis import (
    ForensicSource, ForensicItem, ForensicAnalysisReport, ForensicAlert,
    CommunicationNetwork, ForensicDataType, AnalysisStatus
)
from models.case import Case
from services.audit_service import AuditService

logger = structlog.get_logger()

class ForensicAnalysisService:
    """Service for forensic analysis of digital communications"""
    
    def __init__(self, audit_service: Optional[AuditService] = None):
        """Initialize forensic analysis service"""
        self.audit_service = audit_service
        # Load NLP model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, some NLP features will be limited")
            self.nlp = None
    
    async def process_forensic_source(
        self,
        case_id: int,
        file_path: str,
        source_name: str,
        source_type: str,
        user_id: int
    ) -> ForensicSource:
        """Process a forensic data source (DB file, email archive, etc.)"""
        
        async with AsyncSessionLocal() as db:
            # Calculate file hash for integrity
            file_hash = self._calculate_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            
            # Create forensic source record
            source = ForensicSource(
                case_id=case_id,
                source_name=source_name,
                source_type=source_type,
                file_path=file_path,
                file_size=file_size,
                file_hash=file_hash,
                analysis_status=AnalysisStatus.PENDING,
                uploaded_by_id=user_id
            )
            
            db.add(source)
            await db.commit()
            await db.refresh(source)
            
            # Log audit action if service is available
            if self.audit_service:
                await self.audit_service.log_action(
                    entity_type="forensic_source",
                    entity_id=source.id,
                    action="UPLOAD",
                    user_id=user_id,
                    case_id=case_id,
                    entity_name=source_name
                )
            
            # Start background analysis
            asyncio.create_task(self._analyze_source_background(source.id, case_id, user_id))
            
            logger.info("Forensic source created", source_id=source.id, source_type=source_type)
            return source
    
    async def _analyze_source_background(
        self, 
        source_id: int,
        case_id: int,
        user_id: int
    ) -> None:
        """Background task for forensic source analysis with audit logging"""
        try:
            # Log analysis start
            if self.audit_service:
                await self.audit_service.log_action(
                    entity_type="forensic_source",
                    entity_id=source_id,
                    action="START_ANALYSIS",
                    user_id=user_id,
                    case_id=case_id
                )

            async with AsyncSessionLocal() as db:
                source_result = await db.execute(
                    select(ForensicSource).where(ForensicSource.id == source_id)
                )
                source = source_result.scalar_one_or_none()
                
                if not source:
                    logger.error("Forensic source not found for background analysis", source_id=source_id)
                    return
                
                # Update status to processing
                source.analysis_status = AnalysisStatus.PROCESSING
                await db.commit()
                
                # Step 1: Extract messages based on source type
                logger.info("Starting message extraction", source_id=source_id, type=source.source_type)
                messages = await self._extract_messages(source)
                
                # Step 2: Analyze messages
                logger.info("Analyzing messages", source_id=source_id, count=len(messages))
                analysis_results = await self._analyze_communication_patterns(messages)
                
                # Step 3: Save results and update status
                source.analysis_results = analysis_results
                source.analysis_status = AnalysisStatus.COMPLETED
                source.completed_at = datetime.now(UTC)
                
                await db.commit()
                
                # Log analysis completion
                if self.audit_service:
                    await self.audit_service.log_action(
                        entity_type="forensic_source",
                        entity_id=source_id,
                        action="COMPLETE_ANALYSIS",
                        user_id=user_id,
                        case_id=case_id
                    )
                
                logger.info("Forensic analysis background task completed", source_id=source_id)
                
        except Exception as e:
            logger.error("Background forensic analysis failed", source_id=source_id, error=str(e))
            
            # Log analysis failure
            if self.audit_service:
                try:
                    await self.audit_service.log_action(
                        entity_type="forensic_source",
                        entity_id=source_id,
                        action="FAILED_ANALYSIS",
                        user_id=user_id,
                        case_id=case_id,
                        metadata={"error": str(e)}
                    )
                except Exception as audit_err:
                    logger.error("Failed to log audit action for failed analysis", error=str(audit_err))

            async with AsyncSessionLocal() as db:
                source_result = await db.execute(
                    select(ForensicSource).where(ForensicSource.id == source_id)
                )
                source = source_result.scalar_one_or_none()
                if source:
                    source.analysis_status = AnalysisStatus.FAILED
                    source.error_message = str(e)
                    await db.commit()
    
    async def _analyze_iphone_backup(self, source: ForensicSource, db: AsyncSession):
        """Analyze iPhone backup database"""
        
        # Common iPhone database paths
        db_paths = {
            'sms': '3d0d7e5fb2ce288813306e4d4636395e047a3d28',  # SMS database
            'contacts': '31bb7ba8914766d4ba40d6dfb6113c8b614be442',  # Contacts
            'call_history': '2b2b0084a1bc3a5ac8c27afdf14afb42c61a19ca',  # Call history
            'safari': 'ca3bc056d4da0bbf88b5fb3be254f3b7147e639c',  # Safari history
        }
        
        backup_path = source.file_path
        items_processed = 0
        
        # Process SMS/iMessage database
        sms_db_path = os.path.join(backup_path, db_paths['sms'])
        if os.path.exists(sms_db_path):
            items_processed += await self._process_ios_messages(source, sms_db_path, db)
        
        # Process contacts
        contacts_db_path = os.path.join(backup_path, db_paths['contacts'])
        if os.path.exists(contacts_db_path):
            items_processed += await self._process_ios_contacts(source, contacts_db_path, db)
        
        # Process call history
        call_db_path = os.path.join(backup_path, db_paths['call_history'])
        if os.path.exists(call_db_path):
            items_processed += await self._process_ios_calls(source, call_db_path, db)
        
        # Update device info
        manifest_path = os.path.join(backup_path, 'Manifest.plist')
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'rb') as f:
                    manifest = plistlib.load(f)
                    source.device_info = {
                        'device_name': manifest.get('DeviceName'),
                        'product_type': manifest.get('ProductType'),
                        'product_version': manifest.get('ProductVersion'),
                        'serial_number': manifest.get('SerialNumber'),
                        'backup_date': manifest.get('Date').isoformat() if manifest.get('Date') else None
                    }
            except Exception as e:
                logger.warning("Failed to read manifest", error=str(e))
        
        logger.info("iPhone backup analysis completed", items_processed=items_processed)
    
    async def _process_ios_messages(self, source: ForensicSource, db_path: str, db: AsyncSession) -> int:
        """Process iOS messages database"""
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # Query messages with handles (contacts)
            query = """
            SELECT 
                m.ROWID as message_id,
                m.text,
                m.date,
                m.date_read,
                m.date_delivered,
                m.is_from_me,
                m.is_delivered,
                m.is_read,
                m.service,
                h.id as handle_id,
                c.chat_identifier,
                m.attributedBody
            FROM message m
            LEFT JOIN handle h ON m.handle_id = h.ROWID
            LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            LEFT JOIN chat c ON cmj.chat_id = c.ROWID
            ORDER BY m.date
            """
            
            cursor = conn.execute(query)
            items_processed = 0
            
            for row in cursor:
                # Convert Apple timestamp to datetime
                # Apple timestamps are seconds since 2001-01-01
                apple_timestamp = row['date'] / 1000000000  # Convert nanoseconds to seconds
                timestamp = datetime(2001, 1, 1) + pd.Timedelta(seconds=apple_timestamp)
                
                # Determine message type
                item_type = ForensicDataType.IMESSAGE if row['service'] == 'iMessage' else ForensicDataType.SMS
                
                # Extract participants
                sender = row['handle_id'] if not row['is_from_me'] else 'self'
                recipients = [row['handle_id']] if row['is_from_me'] else ['self']
                
                # Process message content
                content = row['text'] or ''
                if row['attributedBody']:
                    # Handle attributed body (rich text)
                    try:
                        attributed_data = plistlib.loads(row['attributedBody'])
                        if 'NSString' in attributed_data:
                            content = attributed_data['NSString']
                    except:
                        pass
                
                # Analyze content
                analysis_results = await self._analyze_text_content(content, db=db, case_id=source.case_id)
                
                # Create forensic item
                forensic_item = ForensicItem(
                    source_id=source.id,
                    item_type=item_type,
                    external_id=str(row['message_id']),
                    thread_id=row['chat_identifier'],
                    timestamp=timestamp,
                    sender=sender,
                    recipients=recipients,
                    content=content,
                    content_type='text/plain',
                    sentiment_score=analysis_results.get('sentiment'),
                    language=analysis_results.get('language'),
                    keywords=analysis_results.get('keywords'),
                    entities=analysis_results.get('entities'),
                    is_deleted=False,
                    relevance_score=analysis_results.get('relevance', 0.5)
                )
                
                db.add(forensic_item)
                items_processed += 1
                
                # Commit in batches
                if items_processed % 100 == 0:
                    await db.commit()
                    source.analysis_progress = min(50.0, (items_processed / 1000) * 50)
                    await db.commit()
            
            await db.commit()
            return items_processed
            
        finally:
            conn.close()
    
    async def _analyze_email_archive(self, source: ForensicSource, db: AsyncSession):
        """Analyze email archive (mbox, pst, etc.)"""
        
        file_path = source.file_path
        items_processed = 0
        
        try:
            # Handle different email formats
            if file_path.endswith('.mbox'):
                mbox = mailbox.mbox(file_path)
                
                for message in mbox:
                    forensic_item = await self._process_email_message(source, message, db)
                    if forensic_item:
                        db.add(forensic_item)
                        items_processed += 1
                        
                        if items_processed % 50 == 0:
                            await db.commit()
                            source.analysis_progress = min(80.0, (items_processed / 1000) * 80)
                            await db.commit()
            
            elif file_path.endswith('.eml'):
                # Single email file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    message = message_from_string(f.read())
                    forensic_item = await self._process_email_message(source, message, db)
                    if forensic_item:
                        db.add(forensic_item)
                        items_processed = 1
            
            await db.commit()
            logger.info("Email archive analysis completed", items_processed=items_processed)
            
        except Exception as e:
            logger.error("Email analysis failed", error=str(e))
            raise
    
    async def _process_email_message(self, source: ForensicSource, message, db: AsyncSession) -> Optional[ForensicItem]:
        """Process individual email message"""
        
        try:
            # Extract headers
            subject = self._decode_header(message.get('Subject', ''))
            sender = self._decode_header(message.get('From', ''))
            recipients = [self._decode_header(addr) for addr in message.get_all('To', [])]
            cc_recipients = [self._decode_header(addr) for addr in message.get_all('Cc', [])]
            
            # Parse date
            date_str = message.get('Date')
            timestamp = datetime.now(timezone.utc)
            if date_str:
                try:
                    from email.utils import parsedate_to_datetime
                    timestamp = parsedate_to_datetime(date_str)
                except:
                    pass
            
            # Extract content
            content = self._extract_email_content(message)
            
            # Analyze content
            analysis_results = await self._analyze_text_content(content, db=db, case_id=source.case_id)
            
            # Extract attachments info
            attachments = []
            for part in message.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'content_type': part.get_content_type(),
                            'size': len(part.get_payload(decode=True) or b'')
                        })
            
            # Create forensic item
            forensic_item = ForensicItem(
                source_id=source.id,
                item_type=ForensicDataType.EMAIL,
                external_id=message.get('Message-ID', ''),
                timestamp=timestamp,
                sender=sender,
                recipients=recipients + cc_recipients,
                subject=subject,
                content=content,
                content_type='text/html' if '<html' in content.lower() else 'text/plain',
                attachments=attachments,
                headers={
                    'message_id': message.get('Message-ID'),
                    'in_reply_to': message.get('In-Reply-To'),
                    'references': message.get('References'),
                    'x_mailer': message.get('X-Mailer'),
                    'received': message.get_all('Received')
                },
                sentiment_score=analysis_results.get('sentiment'),
                language=analysis_results.get('language'),
                keywords=analysis_results.get('keywords'),
                entities=analysis_results.get('entities'),
                relevance_score=analysis_results.get('relevance', 0.5)
            )
            
            return forensic_item
            
        except Exception as e:
            logger.warning("Failed to process email message", error=str(e))
            return None
    
    async def _analyze_text_content(self, content: str, db: Optional[AsyncSession] = None, case_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Analyze text content for sentiment, entities, keywords"""
        
        # Financial transaction detection if DB and case_id provided
        if db and case_id and content:
            try:
                from services.financial_analysis_service import FinancialAnalysisService
                financial_service = FinancialAnalysisService(db)
                await financial_service.ingest_from_text(case_id, content)
            except Exception as e:
                logger.warning("Financial ingestion failed during forensic text analysis", error=str(e))
        
        if not content or len(content.strip()) == 0:
            return {
                'sentiment': 0.0,
                'language': 'en',
                'keywords': [],
                'entities': [],
                'relevance': 0.1
            }
        
        results = {}
        
        try:
            # Sentiment analysis
            blob = TextBlob(content)
            results['sentiment'] = blob.sentiment.polarity
            
            # Language detection
            try:
                results['language'] = blob.detect_language()
            except:
                results['language'] = 'en'
            
            # Named entity recognition with spaCy
            if self.nlp:
                doc = self.nlp(content[:1000])  # Limit to first 1000 chars for performance
                
                entities = []
                for ent in doc.ents:
                    entities.append({
                        'text': ent.text,
                        'label': ent.label_,
                        'start': ent.start_char,
                        'end': ent.end_char
                    })
                results['entities'] = entities
                
                # Extract keywords (nouns and proper nouns)
                keywords = []
                for token in doc:
                    if token.pos_ in ['NOUN', 'PROPN'] and not token.is_stop and len(token.text) > 2:
                        keywords.append(token.lemma_.lower())
                
                results['keywords'] = list(set(keywords))[:20]  # Top 20 unique keywords
            else:
                results['entities'] = []
                results['keywords'] = []
            
            # Calculate relevance score based on content length and entity count
            relevance = min(1.0, (len(content) / 1000) * 0.5 + (len(results.get('entities', [])) / 10) * 0.5)
            results['relevance'] = max(0.1, relevance)
            
        except Exception as e:
            logger.warning("Text analysis failed", error=str(e))
            results = {
                'sentiment': 0.0,
                'language': 'en',
                'keywords': [],
                'entities': [],
                'relevance': 0.1
            }
        
        return results
    
    async def _generate_analysis_report(self, source: ForensicSource, db: AsyncSession):
        """Generate comprehensive analysis report"""
        
        # Get all forensic items for this source
        items_result = await db.execute(
            select(ForensicItem).where(ForensicItem.source_id == source.id)
        )
        items = items_result.scalars().all()
        
        if not items:
            return
        
        # Calculate statistics
        total_items = len(items)
        date_range = {
            'start': min(item.timestamp for item in items),
            'end': max(item.timestamp for item in items)
        }
        
        # Communication patterns
        communication_stats = self._analyze_communication_patterns(items)
        
        # Sentiment analysis
        sentiment_stats = self._analyze_sentiment_patterns(items)
        
        # Network analysis
        network_data = self._build_communication_network(items)
        
        # Timeline data
        timeline_data = self._build_timeline_data(items)
        
        # Generate insights
        insights = self._generate_insights(items, communication_stats, sentiment_stats)
        
        # Create analysis report
        report = ForensicAnalysisReport(
            source_id=source.id,
            report_type='comprehensive',
            title=f'Forensic Analysis Report - {source.source_name}',
            description=f'Comprehensive analysis of {total_items} items from {source.source_type}',
            total_items=total_items,
            date_range_start=date_range['start'],
            date_range_end=date_range['end'],
            statistics=communication_stats,
            insights=insights,
            network_data=network_data,
            timeline_data=timeline_data,
            charts_data={
                'sentiment_over_time': sentiment_stats,
                'communication_volume': self._get_communication_volume_data(items),
                'top_contacts': self._get_top_contacts_data(items)
            }
        )
        
        db.add(report)
        await db.commit()
        
        logger.info("Analysis report generated", source_id=source.id, total_items=total_items)
    
    async def _generate_forensic_alerts(self, source: ForensicSource, db: AsyncSession):
        """Generate forensic alerts for suspicious patterns (Requirements 5.5)"""
        
        # Get all forensic items for this source
        items_result = await db.execute(
            select(ForensicItem).where(ForensicItem.source_id == source.id)
        )
        items = items_result.scalars().all()
        
        if not items:
            return
        
        # Get communication stats for pattern detection
        communication_stats = self._analyze_communication_patterns(items)
        
        # Detect suspicious patterns
        suspicious_patterns = self._detect_suspicious_patterns(items, communication_stats)
        
        # Create alerts for high and medium severity patterns
        for pattern in suspicious_patterns:
            if pattern.get('severity') in ['high', 'medium']:
                alert = ForensicAlert(
                    source_id=source.id,
                    alert_type=pattern['type'],
                    severity=pattern['severity'],
                    title=pattern['title'],
                    description=pattern['description'],
                    trigger_criteria={
                        'pattern_type': pattern['type'],
                        'detection_method': 'automated_analysis'
                    },
                    affected_items=pattern.get('affected_items', [])
                )
                
                db.add(alert)
        
        await db.commit()
        
        logger.info("Forensic alerts generated", source_id=source.id, alert_count=len([p for p in suspicious_patterns if p.get('severity') in ['high', 'medium']]))
    
    def _analyze_communication_patterns(self, items: List[ForensicItem]) -> Dict[str, Any]:
        """Analyze communication patterns"""
        
        patterns = {
            'total_messages': len(items),
            'by_type': {},
            'by_hour': [0] * 24,
            'by_day_of_week': [0] * 7,
            'by_month': {},
            'top_contacts': {},
            'conversation_threads': {}
        }
        
        for item in items:
            # Count by type
            item_type = item.item_type.value
            patterns['by_type'][item_type] = patterns['by_type'].get(item_type, 0) + 1
            
            # Count by hour
            hour = item.timestamp.hour
            patterns['by_hour'][hour] += 1
            
            # Count by day of week
            day_of_week = item.timestamp.weekday()
            patterns['by_day_of_week'][day_of_week] += 1
            
            # Count by month
            month_key = item.timestamp.strftime('%Y-%m')
            patterns['by_month'][month_key] = patterns['by_month'].get(month_key, 0) + 1
            
            # Count contacts
            if item.sender and item.sender != 'self':
                patterns['top_contacts'][item.sender] = patterns['top_contacts'].get(item.sender, 0) + 1
            
            for recipient in (item.recipients or []):
                if recipient != 'self':
                    patterns['top_contacts'][recipient] = patterns['top_contacts'].get(recipient, 0) + 1
            
            # Count conversation threads
            if item.thread_id:
                patterns['conversation_threads'][item.thread_id] = patterns['conversation_threads'].get(item.thread_id, 0) + 1
        
        # Sort top contacts
        patterns['top_contacts'] = dict(sorted(patterns['top_contacts'].items(), key=lambda x: x[1], reverse=True)[:20])
        
        return patterns
    
    def _analyze_sentiment_patterns(self, items: List[ForensicItem]) -> Dict[str, Any]:
        """Analyze sentiment patterns over time"""
        
        sentiment_data = []
        for item in items:
            if item.sentiment_score is not None:
                sentiment_data.append({
                    'date': item.timestamp.isoformat(),
                    'sentiment': item.sentiment_score,
                    'contact': item.sender if item.sender != 'self' else (item.recipients[0] if item.recipients else 'unknown')
                })
        
        return sentiment_data
    
    def _build_communication_network(self, items: List[ForensicItem]) -> Dict[str, Any]:
        """Build communication network graph"""
        
        G = nx.Graph()
        
        for item in items:
            sender = item.sender or 'unknown'
            recipients = item.recipients or []
            
            # Add nodes
            G.add_node(sender)
            for recipient in recipients:
                G.add_node(recipient)
                
                # Add edge with weight
                if G.has_edge(sender, recipient):
                    G[sender][recipient]['weight'] += 1
                else:
                    G.add_edge(sender, recipient, weight=1)
        
        # Calculate network metrics
        centrality = nx.degree_centrality(G)
        betweenness = nx.betweenness_centrality(G)
        
        # Convert to serializable format
        nodes = []
        for node in G.nodes():
            nodes.append({
                'id': node,
                'degree_centrality': centrality.get(node, 0),
                'betweenness_centrality': betweenness.get(node, 0)
            })
        
        edges = []
        for edge in G.edges(data=True):
            edges.append({
                'source': edge[0],
                'target': edge[1],
                'weight': edge[2]['weight']
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'metrics': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'density': nx.density(G),
                'average_clustering': nx.average_clustering(G) if len(nodes) > 2 else 0
            }
        }
    
    def _build_timeline_data(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Build timeline visualization data"""
        
        timeline_items = []
        for item in items:
            timeline_items.append({
                'id': item.id,
                'timestamp': item.timestamp.isoformat(),
                'type': item.item_type.value,
                'sender': item.sender,
                'recipients': item.recipients,
                'subject': item.subject,
                'content_preview': (item.content or '')[:100],
                'sentiment': item.sentiment_score,
                'relevance': item.relevance_score
            })
        
        return sorted(timeline_items, key=lambda x: x['timestamp'])
    
    def _generate_insights(self, items: List[ForensicItem], comm_stats: Dict, sentiment_stats: Dict) -> List[Dict[str, Any]]:
        """Generate AI insights from analysis"""
        
        insights = []
        
        # Communication volume insights
        total_messages = len(items)
        if total_messages > 0:
            insights.append({
                'type': 'volume',
                'title': 'Communication Volume',
                'description': f'Analyzed {total_messages} communication items',
                'severity': 'info'
            })
        
        # Peak activity insights
        hourly_counts = comm_stats.get('by_hour', [])
        peak_hour = hourly_counts.index(max(hourly_counts)) if hourly_counts else 0
        insights.append({
            'type': 'pattern',
            'title': 'Peak Activity Time',
            'description': f'Most active communication occurs at {peak_hour}:00',
            'severity': 'info'
        })
        
        # Enhanced suspicious pattern detection
        suspicious_patterns = self._detect_suspicious_patterns(items, comm_stats)
        insights.extend(suspicious_patterns)
        
        return insights
    
    def _detect_suspicious_patterns(self, items: List[ForensicItem], comm_stats: Dict) -> List[Dict[str, Any]]:
        """Detect suspicious patterns in forensic data (Requirements 5.5)"""
        
        patterns = []
        total_messages = len(items)
        
        if total_messages == 0:
            return patterns
        
        # 1. Deleted messages pattern
        deleted_items = [item for item in items if item.is_deleted]
        if deleted_items:
            patterns.append({
                'type': 'suspicious',
                'title': 'Deleted Messages Found',
                'description': f'{len(deleted_items)} deleted messages recovered',
                'severity': 'high',
                'affected_items': [item.id for item in deleted_items]
            })
        
        # 2. Negative sentiment spikes
        negative_items = [item for item in items if item.sentiment_score and item.sentiment_score < -0.3]
        if len(negative_items) > total_messages * 0.2:  # More than 20% negative
            patterns.append({
                'type': 'sentiment',
                'title': 'High Negative Sentiment',
                'description': f'{len(negative_items)} messages show strong negative sentiment',
                'severity': 'warning',
                'affected_items': [item.id for item in negative_items]
            })
        
        # 3. Unusual timing patterns
        timing_anomalies = self._detect_timing_anomalies(items)
        patterns.extend(timing_anomalies)
        
        # 4. Communication frequency anomalies
        frequency_anomalies = self._detect_frequency_anomalies(items, comm_stats)
        patterns.extend(frequency_anomalies)
        
        # 5. Content-based suspicious patterns
        content_anomalies = self._detect_content_anomalies(items)
        patterns.extend(content_anomalies)
        
        # 6. Participant behavior anomalies
        participant_anomalies = self._detect_participant_anomalies(items)
        patterns.extend(participant_anomalies)
        
        return patterns
    
    def _detect_timing_anomalies(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Detect unusual timing patterns in communications"""
        
        anomalies = []
        
        if len(items) < 10:  # Need sufficient data for timing analysis
            return anomalies
        
        # Sort items by timestamp
        sorted_items = sorted(items, key=lambda x: x.timestamp)
        
        # Detect unusual late-night activity (11 PM - 5 AM)
        late_night_items = [
            item for item in items 
            if item.timestamp.hour >= 23 or item.timestamp.hour <= 5
        ]
        
        if len(late_night_items) > len(items) * 0.3:  # More than 30% late night
            anomalies.append({
                'type': 'timing',
                'title': 'Unusual Late-Night Activity',
                'description': f'{len(late_night_items)} messages sent during late night hours (11 PM - 5 AM)',
                'severity': 'medium',
                'affected_items': [item.id for item in late_night_items]
            })
        
        # Detect rapid-fire messaging (many messages in short time)
        rapid_sequences = []
        current_sequence = []
        
        for i in range(1, len(sorted_items)):
            time_diff = (sorted_items[i].timestamp - sorted_items[i-1].timestamp).total_seconds()
            
            if time_diff < 60:  # Less than 1 minute apart
                if not current_sequence:
                    current_sequence = [sorted_items[i-1]]
                current_sequence.append(sorted_items[i])
            else:
                if len(current_sequence) >= 5:  # 5+ messages in rapid succession
                    rapid_sequences.append(current_sequence)
                current_sequence = []
        
        # Check final sequence
        if len(current_sequence) >= 5:
            rapid_sequences.append(current_sequence)
        
        if rapid_sequences:
            total_rapid_messages = sum(len(seq) for seq in rapid_sequences)
            anomalies.append({
                'type': 'timing',
                'title': 'Rapid-Fire Messaging Detected',
                'description': f'{total_rapid_messages} messages sent in {len(rapid_sequences)} rapid sequences',
                'severity': 'medium',
                'affected_items': [item.id for seq in rapid_sequences for item in seq]
            })
        
        # Detect long communication gaps followed by sudden activity
        gaps = []
        for i in range(1, len(sorted_items)):
            time_diff = (sorted_items[i].timestamp - sorted_items[i-1].timestamp).total_seconds()
            if time_diff > 86400 * 7:  # More than 7 days gap
                gaps.append((sorted_items[i-1], sorted_items[i], time_diff))
        
        if gaps:
            anomalies.append({
                'type': 'timing',
                'title': 'Communication Gaps Detected',
                'description': f'{len(gaps)} significant communication gaps (>7 days) followed by resumed activity',
                'severity': 'low',
                'affected_items': [gap[1].id for gap in gaps]
            })
        
        return anomalies
    
    def _detect_frequency_anomalies(self, items: List[ForensicItem], comm_stats: Dict) -> List[Dict[str, Any]]:
        """Detect unusual communication frequency patterns"""
        
        anomalies = []
        
        # Analyze daily communication volume
        daily_volumes = comm_stats.get('by_month', {})
        if not daily_volumes:
            return anomalies
        
        volumes = list(daily_volumes.values())
        if len(volumes) < 3:
            return anomalies
        
        # Calculate average and detect spikes
        avg_volume = sum(volumes) / len(volumes)
        std_dev = (sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)) ** 0.5
        
        # Detect volume spikes (more than 2 standard deviations above average)
        spike_threshold = avg_volume + (2 * std_dev)
        spikes = [(date, vol) for date, vol in daily_volumes.items() if vol > spike_threshold]
        
        if spikes:
            anomalies.append({
                'type': 'frequency',
                'title': 'Communication Volume Spikes',
                'description': f'{len(spikes)} periods with unusually high communication volume',
                'severity': 'medium',
                'details': spikes
            })
        
        return anomalies
    
    def _detect_content_anomalies(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Detect suspicious content patterns"""
        
        anomalies = []
        
        # Detect messages with suspicious keywords
        suspicious_keywords = [
            'delete', 'destroy', 'hide', 'cover up', 'secret', 'confidential',
            'don\'t tell', 'between us', 'off the record', 'cash only',
            'no paper trail', 'untraceable', 'anonymous'
        ]
        
        suspicious_items = []
        for item in items:
            if item.content:
                content_lower = item.content.lower()
                for keyword in suspicious_keywords:
                    if keyword in content_lower:
                        suspicious_items.append(item)
                        break
        
        if suspicious_items:
            anomalies.append({
                'type': 'content',
                'title': 'Suspicious Keywords Detected',
                'description': f'{len(suspicious_items)} messages contain potentially suspicious keywords',
                'severity': 'high',
                'affected_items': [item.id for item in suspicious_items]
            })
        
        # Detect encrypted or encoded messages
        encrypted_items = [item for item in items if item.is_encrypted]
        if encrypted_items:
            anomalies.append({
                'type': 'content',
                'title': 'Encrypted Messages Found',
                'description': f'{len(encrypted_items)} encrypted messages detected',
                'severity': 'medium',
                'affected_items': [item.id for item in encrypted_items]
            })
        
        # Detect very short messages (potential codes)
        short_items = [
            item for item in items 
            if item.content and len(item.content.strip()) <= 10 and len(item.content.strip()) > 0
        ]
        
        if len(short_items) > len(items) * 0.4:  # More than 40% very short messages
            anomalies.append({
                'type': 'content',
                'title': 'Unusually Short Messages',
                'description': f'{len(short_items)} very short messages (≤10 characters) - potential coded communication',
                'severity': 'medium',
                'affected_items': [item.id for item in short_items]
            })
        
        return anomalies
    
    def _detect_participant_anomalies(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Detect unusual participant behavior patterns"""
        
        anomalies = []
        
        # Analyze participant communication patterns
        participant_stats = {}
        
        for item in items:
            sender = item.sender or 'unknown'
            recipients = item.recipients or []
            
            if sender not in participant_stats:
                participant_stats[sender] = {
                    'sent': 0, 'received': 0, 'contacts': set(),
                    'sentiment_scores': [], 'late_night': 0
                }
            
            participant_stats[sender]['sent'] += 1
            participant_stats[sender]['contacts'].update(recipients)
            
            if item.sentiment_score is not None:
                participant_stats[sender]['sentiment_scores'].append(item.sentiment_score)
            
            if item.timestamp.hour >= 23 or item.timestamp.hour <= 5:
                participant_stats[sender]['late_night'] += 1
            
            # Track received messages
            for recipient in recipients:
                if recipient not in participant_stats:
                    participant_stats[recipient] = {
                        'sent': 0, 'received': 0, 'contacts': set(),
                        'sentiment_scores': [], 'late_night': 0
                    }
                participant_stats[recipient]['received'] += 1
                participant_stats[recipient]['contacts'].add(sender)
        
        # Detect participants with unusual behavior
        for participant, stats in participant_stats.items():
            total_messages = stats['sent'] + stats['received']
            
            # Detect participants who only send (never receive)
            if stats['sent'] > 5 and stats['received'] == 0:
                anomalies.append({
                    'type': 'participant',
                    'title': 'One-Way Communication Pattern',
                    'description': f'Participant {participant} only sends messages (never receives)',
                    'severity': 'medium',
                    'participant': participant
                })
            
            # Detect participants with consistently negative sentiment
            if len(stats['sentiment_scores']) > 5:
                avg_sentiment = sum(stats['sentiment_scores']) / len(stats['sentiment_scores'])
                if avg_sentiment < -0.5:
                    anomalies.append({
                        'type': 'participant',
                        'title': 'Consistently Negative Sentiment',
                        'description': f'Participant {participant} shows consistently negative sentiment (avg: {avg_sentiment:.2f})',
                        'severity': 'medium',
                        'participant': participant
                    })
            
            # Detect participants with excessive late-night activity
            if total_messages > 10 and stats['late_night'] / total_messages > 0.5:
                anomalies.append({
                    'type': 'participant',
                    'title': 'Excessive Late-Night Activity',
                    'description': f'Participant {participant} has {stats["late_night"]} late-night messages ({stats["late_night"]/total_messages*100:.1f}%)',
                    'severity': 'low',
                    'participant': participant
                })
        
        return anomalies
    
    def _get_communication_volume_data(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Get communication volume over time"""
        
        volume_data = {}
        for item in items:
            date_key = item.timestamp.strftime('%Y-%m-%d')
            volume_data[date_key] = volume_data.get(date_key, 0) + 1
        
        return [{'date': date, 'count': count} for date, count in sorted(volume_data.items())]
    
    def _get_top_contacts_data(self, items: List[ForensicItem]) -> List[Dict[str, Any]]:
        """Get top contacts by message count"""
        
        contacts = {}
        for item in items:
            if item.sender and item.sender != 'self':
                contacts[item.sender] = contacts.get(item.sender, 0) + 1
            
            for recipient in (item.recipients or []):
                if recipient != 'self':
                    contacts[recipient] = contacts.get(recipient, 0) + 1
        
        return [{'contact': contact, 'count': count} 
                for contact, count in sorted(contacts.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header value"""
        
        if not header_value:
            return ''
        
        decoded_parts = decode_header(header_value)
        decoded_string = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string
    
    def _extract_email_content(self, message) -> str:
        """Extract text content from email message"""
        
        content = ''
        
        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        content += payload.decode('utf-8', errors='ignore')
                elif content_type == 'text/html' and not content:
                    # Use HTML if no plain text available
                    payload = part.get_payload(decode=True)
                    if payload:
                        content += payload.decode('utf-8', errors='ignore')
        else:
            payload = message.get_payload(decode=True)
            if payload:
                content = payload.decode('utf-8', errors='ignore')
        
        return content