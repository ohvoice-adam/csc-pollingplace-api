"""
Automated Alerting System

Provides automated alerting for critical errors and system issues.
Supports multiple alert channels including email, Slack, webhooks, and SMS.
"""

import time
import json
import asyncio
import smtplib
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import logging

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from redis import Redis as RedisType
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisType = None

# Import with fallback
try:
    from structured_logging import get_logger
    from error_tracking import error_tracker
except ImportError:
    def get_logger(name):
        return logging.getLogger(name)
    error_tracker = None

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertChannel:
    """Alert channel configuration"""
    name: str
    type: str  # email, slack, webhook, sms
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit: int = 300  # seconds between alerts
    last_sent: Optional[datetime] = None


@dataclass
class Alert:
    """Alert definition"""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    source: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    condition: str  # Python expression
    severity: AlertSeverity
    enabled: bool = True
    cooldown: int = 300  # seconds
    channels: List[str] = field(default_factory=list)
    threshold: int = 1
    time_window: int = 300  # seconds
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


class AlertManager:
    """Manages automated alerting system"""
    
    def __init__(self, redis_client: Optional[RedisType] = None):
        self.redis_client = redis_client
        self.channels: Dict[str, AlertChannel] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.suppression_rules: Dict[str, Dict[str, Any]] = {}
        
        # Default settings
        self.default_settings = {
            'max_alerts_per_hour': 100,
            'alert_retention_days': 30,
            'auto_resolve_hours': 24,
            'escalation_enabled': True,
            'deduplication_enabled': True
        }
    
    def add_channel(self, channel: AlertChannel):
        """Add an alert channel"""
        self.channels[channel.name] = channel
        logger.info("Added alert channel", channel=channel.name, type=channel.type)
    
    def add_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.rules[rule.name] = rule
        logger.info("Added alert rule", rule=rule.name, severity=rule.severity.value)
    
    def create_alert(self, title: str, description: str, severity: AlertSeverity,
                    source: str = "", context: Optional[Dict[str, Any]] = None,
                    tags: Optional[List[str]] = None) -> Alert:
        """Create a new alert"""
        alert_id = f"{int(time.time())}_{hash(title) % 10000}"
        
        alert = Alert(
            id=alert_id,
            title=title,
            description=description,
            severity=severity,
            source=source,
            context=context or {},
            tags=tags or []
        )
        
        # Check for deduplication
        if self.default_settings['deduplication_enabled']:
            existing = self._find_duplicate_alert(alert)
            if existing:
                logger.info("Alert deduplicated", existing_id=existing.id, new_id=alert_id)
                return existing
        
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        
        logger.warning("Alert created", 
                      alert_id=alert_id, title=title, severity=severity.value)
        
        # Trigger notifications
        self._send_alert_notifications(alert)
        
        return alert
    
    def _find_duplicate_alert(self, new_alert: Alert) -> Optional[Alert]:
        """Find duplicate existing alert"""
        for alert in self.active_alerts.values():
            if (alert.title == new_alert.title and 
                alert.status == AlertStatus.ACTIVE and
                alert.severity == new_alert.severity):
                # Update existing alert
                alert.updated_at = datetime.utcnow()
                alert.context.update(new_alert.context)
                return alert
        return None
    
    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        logger.info("Alert acknowledged", alert_id=alert_id, user=user)
        return True
    
    def resolve_alert(self, alert_id: str, user: str = "system") -> bool:
        """Resolve an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        # Move from active to resolved
        del self.active_alerts[alert_id]
        
        logger.info("Alert resolved", alert_id=alert_id, user=user)
        return True
    
    def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications through configured channels"""
        # Find applicable rules
        applicable_rules = [
            rule for rule in self.rules.values() 
            if rule.enabled and self._evaluate_rule(rule, alert)
        ]
        
        if not applicable_rules:
            # Use default channels if no rules match
            channels = [ch for ch in self.channels.values() if ch.enabled]
        else:
            # Use channels from matching rules
            channel_names = set()
            for rule in applicable_rules:
                channel_names.update(rule.channels)
            channels = [self.channels[name] for name in channel_names if name in self.channels]
        
        # Send notifications
        for channel in channels:
            if self._should_send_notification(channel, alert):
                try:
                    self._send_notification(channel, alert)
                    channel.last_sent = datetime.utcnow()
                except Exception as e:
                    logger.error("Failed to send notification", 
                                channel=channel.name, alert_id=alert.id, error=str(e))
    
    def _evaluate_rule(self, rule: AlertRule, alert: Alert) -> bool:
        """Evaluate if alert matches rule"""
        try:
            # Simple evaluation - can be extended
            context = {
                'alert': alert,
                'severity': alert.severity.value,
                'title': alert.title,
                'source': alert.source,
                'tags': alert.tags
            }
            
            # Check cooldown
            if (rule.last_triggered and 
                (datetime.utcnow() - rule.last_triggered).seconds < rule.cooldown):
                return False
            
            # Evaluate condition
            result = eval(rule.condition, {"__builtins__": {}}, context)
            
            if result:
                rule.last_triggered = datetime.utcnow()
                rule.trigger_count += 1
            
            return result
            
        except Exception as e:
            logger.error("Error evaluating alert rule", rule=rule.name, error=str(e))
            return False
    
    def _should_send_notification(self, channel: AlertChannel, alert: Alert) -> bool:
        """Check if notification should be sent"""
        if not channel.enabled:
            return False
        
        # Check rate limiting
        if (channel.last_sent and 
            (datetime.utcnow() - channel.last_sent).seconds < channel.rate_limit):
            return False
        
        # Check suppression rules
        for rule_name, rule_config in self.suppression_rules.items():
            if self._matches_suppression_rule(alert, rule_config):
                return False
        
        return True
    
    def _matches_suppression_rule(self, alert: Alert, rule: Dict[str, Any]) -> bool:
        """Check if alert matches suppression rule"""
        # Check severity
        if 'severity' in rule:
            if isinstance(rule['severity'], list):
                if alert.severity.value not in rule['severity']:
                    return False
            elif alert.severity.value != rule['severity']:
                return False
        
        # Check source
        if 'source' in rule and alert.source != rule['source']:
            return False
        
        # Check tags
        if 'tags' in rule:
            required_tags = set(rule['tags'])
            if not required_tags.issubset(set(alert.tags)):
                return False
        
        # Check time window
        if 'time_window' in rule:
            start_time = datetime.utcnow() - timedelta(seconds=rule['time_window'])
            if alert.created_at < start_time:
                return False
        
        return True
    
    def _send_notification(self, channel: AlertChannel, alert: Alert):
        """Send notification through specific channel"""
        if channel.type == "email":
            self._send_email_notification(channel, alert)
        elif channel.type == "slack":
            self._send_slack_notification(channel, alert)
        elif channel.type == "webhook":
            self._send_webhook_notification(channel, alert)
        elif channel.type == "sms":
            self._send_sms_notification(channel, alert)
        else:
            logger.warning("Unknown alert channel type", type=channel.type)
    
    def _send_email_notification(self, channel: AlertChannel, alert: Alert):
        """Send email notification"""
        if not REQUESTS_AVAILABLE:
            logger.error("Email notification requires requests")
            return
        
        config = channel.config
        required_fields = ['smtp_server', 'smtp_port', 'username', 'password', 'to']
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field for email: {field}")
        
        # Create message
        msg = MimeMultipart()
        msg['From'] = config['username']
        msg['To'] = ', '.join(config['to'])
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
        
        # Create body
        body = f"""
Alert Details:
- Title: {alert.title}
- Severity: {alert.severity.value}
- Source: {alert.source}
- Description: {alert.description}
- Time: {alert.created_at.isoformat()}
- Alert ID: {alert.id}

Context:
{json.dumps(alert.context, indent=2)}

Tags: {', '.join(alert.tags)}
"""
        
        msg.attach(MimeText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)
        
        logger.info("Email notification sent", alert_id=alert.id, to=config['to'])
    
    def _send_slack_notification(self, channel: AlertChannel, alert: Alert):
        """Send Slack notification"""
        if not REQUESTS_AVAILABLE:
            logger.error("Slack notification requires requests")
            return
        
        config = channel.config
        if 'webhook_url' not in config:
            raise ValueError("Missing webhook_url for Slack channel")
        
        # Color based on severity
        color_map = {
            AlertSeverity.LOW: "good",
            AlertSeverity.MEDIUM: "warning",
            AlertSeverity.HIGH: "danger",
            AlertSeverity.CRITICAL: "#ff0000"
        }
        
        payload = {
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "warning"),
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "text": alert.description,
                    "fields": [
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Alert ID", "value": alert.id, "short": True},
                        {"title": "Time", "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True},
                        {"title": "Tags", "value": ", ".join(alert.tags), "short": True}
                    ],
                    "footer": "CSC PollingPlace API",
                    "ts": int(alert.created_at.timestamp())
                }
            ]
        }
        
        response = requests.post(config['webhook_url'], json=payload)
        response.raise_for_status()
        
        logger.info("Slack notification sent", alert_id=alert.id)
    
    def _send_webhook_notification(self, channel: AlertChannel, alert: Alert):
        """Send webhook notification"""
        if not REQUESTS_AVAILABLE:
            logger.error("Webhook notification requires requests")
            return
        
        config = channel.config
        if 'url' not in config:
            raise ValueError("Missing url for webhook channel")
        
        payload = {
            "alert_id": alert.id,
            "title": alert.title,
            "description": alert.description,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "source": alert.source,
            "context": alert.context,
            "tags": alert.tags,
            "created_at": alert.created_at.isoformat(),
            "updated_at": alert.updated_at.isoformat()
        }
        
        headers = config.get('headers', {})
        response = requests.post(config['url'], json=payload, headers=headers)
        response.raise_for_status()
        
        logger.info("Webhook notification sent", alert_id=alert.id, url=config['url'])
    
    def _send_sms_notification(self, channel: AlertChannel, alert: Alert):
        """Send SMS notification"""
        if not REQUESTS_AVAILABLE:
            logger.error("SMS notification requires requests")
            return
        
        config = channel.config
        if 'url' not in config or 'phone_numbers' not in config:
            raise ValueError("Missing url or phone_numbers for SMS channel")
        
        message = f"[{alert.severity.value.upper()}] {alert.title}: {alert.description}"
        
        for phone in config['phone_numbers']:
            payload = {
                'phone': phone,
                'message': message
            }
            
            # Add any additional config fields
            payload.update({k: v for k, v in config.items() 
                          if k not in ['url', 'phone_numbers']})
            
            response = requests.post(config['url'], json=payload)
            response.raise_for_status()
        
        logger.info("SMS notification sent", alert_id=alert.id, 
                   phones=len(config['phone_numbers']))
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        recent_alerts = [a for a in self.alert_history if a.created_at >= last_24h]
        weekly_alerts = [a for a in self.alert_history if a.created_at >= last_7d]
        
        severity_counts = {}
        for severity in AlertSeverity:
            severity_counts[severity.value] = len([
                a for a in recent_alerts if a.severity == severity
            ])
        
        return {
            "total_active": len(self.active_alerts),
            "last_24h": len(recent_alerts),
            "last_7d": len(weekly_alerts),
            "severity_breakdown": severity_counts,
            "channels_configured": len(self.channels),
            "rules_configured": len(self.rules),
            "acknowledged": len([a for a in self.active_alerts.values() 
                               if a.status == AlertStatus.ACKNOWLEDGED])
        }
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity"""
        alerts = list(self.active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
    
    def cleanup_old_alerts(self):
        """Clean up old resolved alerts"""
        retention_days = self.default_settings['alert_retention_days']
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        original_count = len(self.alert_history)
        self.alert_history = [
            alert for alert in self.alert_history 
            if alert.created_at > cutoff_date or alert.status == AlertStatus.ACTIVE
        ]
        
        cleaned_count = original_count - len(self.alert_history)
        if cleaned_count > 0:
            logger.info("Cleaned up old alerts", count=cleaned_count)


# Global instance
alert_manager = AlertManager()


# Convenience functions
def create_alert(title: str, description: str, severity: AlertSeverity,
                source: str = "", context: Optional[Dict[str, Any]] = None,
                tags: Optional[List[str]] = None) -> Alert:
    """Create an alert using the global alert manager"""
    return alert_manager.create_alert(title, description, severity, source, context, tags)


def setup_default_channels():
    """Setup default alert channels"""
    # Email channel (example configuration)
    email_channel = AlertChannel(
        name="email",
        type="email",
        enabled=False,  # Disabled by default
        config={
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "alerts@example.com",
            "password": "your_password",
            "to": ["admin@example.com"]
        }
    )
    
    # Slack channel (example configuration)
    slack_channel = AlertChannel(
        name="slack",
        type="slack",
        enabled=False,  # Disabled by default
        config={
            "webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
        }
    )
    
    alert_manager.add_channel(email_channel)
    alert_manager.add_channel(slack_channel)


def setup_default_rules():
    """Setup default alert rules"""
    # Critical error rule
    critical_rule = AlertRule(
        name="critical_errors",
        condition="severity == 'critical'",
        severity=AlertSeverity.CRITICAL,
        channels=["email", "slack"],
        cooldown=60  # 1 minute
    )
    
    # High error rate rule
    error_rate_rule = AlertRule(
        name="high_error_rate",
        condition="'error_rate' in alert.context and alert.context['error_rate'] > 0.1",
        severity=AlertSeverity.HIGH,
        channels=["slack"],
        cooldown=300  # 5 minutes
    )
    
    alert_manager.add_rule(critical_rule)
    alert_manager.add_rule(error_rate_rule)