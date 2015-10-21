Class.extend({
	init: function()
	{
		this.state = {
			newidx:  0,
			values:  { },
			creates: { },
			changes: { },
			deletes: { },
			reorder: { }
		};
	},

	callLoad: L.rpc.declare({
		object: 'uci',
		method: 'get',
		params: [ 'config' ],
		expect: { values: { } }
	}),

	callOrder: L.rpc.declare({
		object: 'uci',
		method: 'order',
		params: [ 'config', 'sections' ]
	}),

	callAdd: L.rpc.declare({
		object: 'uci',
		method: 'add',
		params: [ 'config', 'type', 'name', 'values' ],
		expect: { section: '' }
	}),

	callSet: L.rpc.declare({
		object: 'uci',
		method: 'set',
		params: [ 'config', 'section', 'values' ]
	}),

	callDelete: L.rpc.declare({
		object: 'uci',
		method: 'delete',
		params: [ 'config', 'section', 'options' ]
	}),

	callApply: L.rpc.declare({
		object: 'uci',
		method: 'apply',
		params: [ 'timeout', 'rollback' ]
	}),

	callConfirm: L.rpc.declare({
		object: 'uci',
		method: 'confirm'
	}),

	createSID: function(conf)
	{
		var v = this.state.values;
		var n = this.state.creates;
		var sid;

		do {
			sid = "new%06x".format(Math.random() * 0xFFFFFF);
		} while ((n[conf] && n[conf][sid]) || (v[conf] && v[conf][sid]));

		return sid;
	},

	reorderSections: function()
	{
		var v = this.state.values;
		var n = this.state.creates;
		var r = this.state.reorder;

		if ($.isEmptyObject(r))
			return L.deferrable();

		L.rpc.batch();

		/*
		 gather all created and existing sections, sort them according
		 to their index value and issue an uci order call
		*/
		for (var c in r)
		{
			var o = [ ];

			if (n[c])
				for (var s in n[c])
					o.push(n[c][s]);

			for (var s in v[c])
				o.push(v[c][s]);

			if (o.length > 0)
			{
				o.sort(function(a, b) {
					return (a['.index'] - b['.index']);
				});

				var sids = [ ];

				for (var i = 0; i < o.length; i++)
					sids.push(o[i]['.name']);

				this.callOrder(c, sids);
			}
		}

		this.state.reorder = { };
		return L.rpc.flush();
	},

	load: function(packages)
	{
		var self = this;
		var seen = { };
		var pkgs = [ ];

		if (!$.isArray(packages))
			packages = [ packages ];

		L.rpc.batch();

		for (var i = 0; i < packages.length; i++)
			if (!seen[packages[i]] && !self.state.values[packages[i]])
			{
				pkgs.push(packages[i]);
				seen[packages[i]] = true;
				self.callLoad(packages[i]);
			}

		return L.rpc.flush().then(function(responses) {
			for (var i = 0; i < responses.length; i++)
				self.state.values[pkgs[i]] = responses[i];

			return pkgs;
		});
	},

	unload: function(packages)
	{
		if (!$.isArray(packages))
			packages = [ packages ];

		for (var i = 0; i < packages.length; i++)
		{
			delete this.state.values[packages[i]];
			delete this.state.creates[packages[i]];
			delete this.state.changes[packages[i]];
			delete this.state.deletes[packages[i]];
		}
	},

	add: function(conf, type, name)
	{
		var n = this.state.creates;
		var sid = name || this.createSID(conf);

		if (!n[conf])
			n[conf] = { };

		n[conf][sid] = {
			'.type':      type,
			'.name':      sid,
			'.create':    name,
			'.anonymous': !name,
			'.index':     1000 + this.state.newidx++
		};

		return sid;
	},

	remove: function(conf, sid)
	{
		var n = this.state.creates;
		var c = this.state.changes;
		var d = this.state.deletes;

		/* requested deletion of a just created section */
		if (n[conf] && n[conf][sid])
		{
			delete n[conf][sid];
		}
		else
		{
			if (c[conf])
				delete c[conf][sid];

			if (!d[conf])
				d[conf] = { };

			d[conf][sid] = true;
		}
	},

	sections: function(conf, type, cb)
	{
		var sa = [ ];
		var v = this.state.values[conf];
		var n = this.state.creates[conf];
		var c = this.state.changes[conf];
		var d = this.state.deletes[conf];

		if (!v)
			return sa;

		for (var s in v)
			if (!d || d[s] !== true)
				if (!type || v[s]['.type'] == type)
					sa.push($.extend({ }, v[s], c ? c[s] : undefined));

		if (n)
			for (var s in n)
				if (!type || n[s]['.type'] == type)
					sa.push(n[s]);

		sa.sort(function(a, b) {
			return a['.index'] - b['.index'];
		});

		for (var i = 0; i < sa.length; i++)
			sa[i]['.index'] = i;

		if (typeof(cb) == 'function')
			for (var i = 0; i < sa.length; i++)
				cb.call(this, sa[i], sa[i]['.name']);

		return sa;
	},

	get: function(conf, sid, opt)
	{
		var v = this.state.values;
		var n = this.state.creates;
		var c = this.state.changes;
		var d = this.state.deletes;

		if (typeof(sid) == 'undefined')
			return undefined;

		/* requested option in a just created section */
		if (n[conf] && n[conf][sid])
		{
			if (!n[conf])
				return undefined;

			if (typeof(opt) == 'undefined')
				return n[conf][sid];

			return n[conf][sid][opt];
		}

		/* requested an option value */
		if (typeof(opt) != 'undefined')
		{
			/* check whether option was deleted */
			if (d[conf] && d[conf][sid])
			{
				if (d[conf][sid] === true)
					return undefined;

				for (var i = 0; i < d[conf][sid].length; i++)
					if (d[conf][sid][i] == opt)
						return undefined;
			}

			/* check whether option was changed */
			if (c[conf] && c[conf][sid] && typeof(c[conf][sid][opt]) != 'undefined')
				return c[conf][sid][opt];

			/* return base value */
			if (v[conf] && v[conf][sid])
				return v[conf][sid][opt];

			return undefined;
		}

		/* requested an entire section */
		if (v[conf])
			return v[conf][sid];

		return undefined;
	},

	set: function(conf, sid, opt, val)
	{
		var v = this.state.values;
		var n = this.state.creates;
		var c = this.state.changes;
		var d = this.state.deletes;

		if (typeof(sid) == 'undefined' ||
			typeof(opt) == 'undefined' ||
			opt.charAt(0) == '.')
			return;

		if (n[conf] && n[conf][sid])
		{
			if (typeof(val) != 'undefined')
				n[conf][sid][opt] = val;
			else
				delete n[conf][sid][opt];
		}
		else if (typeof(val) != 'undefined' && val !== '')
		{
			/* do not set within deleted section */
			if (d[conf] && d[conf][sid] === true)
				return;

			/* only set in existing sections */
			if (!v[conf] || !v[conf][sid])
				return;

			if (!c[conf])
				c[conf] = { };

			if (!c[conf][sid])
				c[conf][sid] = { };

			/* undelete option */
			if (d[conf] && d[conf][sid])
				d[conf][sid] = L.filterArray(d[conf][sid], opt);

			c[conf][sid][opt] = val;
		}
		else
		{
			/* only delete in existing sections */
			if (!v[conf] || !v[conf][sid])
				return;

			if (!d[conf])
				d[conf] = { };

			if (!d[conf][sid])
				d[conf][sid] = [ ];

			if (d[conf][sid] !== true)
				d[conf][sid].push(opt);
		}
	},

	unset: function(conf, sid, opt)
	{
		return this.set(conf, sid, opt, undefined);
	},

	get_first: function(conf, type, opt)
	{
		var sid = undefined;

		L.uci.sections(conf, type, function(s) {
			if (typeof(sid) != 'string')
				sid = s['.name'];
		});

		return this.get(conf, sid, opt);
	},

	set_first: function(conf, type, opt, val)
	{
		var sid = undefined;

		L.uci.sections(conf, type, function(s) {
			if (typeof(sid) != 'string')
				sid = s['.name'];
		});

		return this.set(conf, sid, opt, val);
	},

	unset_first: function(conf, type, opt)
	{
		return this.set_first(conf, type, opt, undefined);
	},

	swap: function(conf, sid1, sid2)
	{
		var s1 = this.get(conf, sid1);
		var s2 = this.get(conf, sid2);
		var n1 = s1 ? s1['.index'] : NaN;
		var n2 = s2 ? s2['.index'] : NaN;

		if (isNaN(n1) || isNaN(n2))
			return false;

		s1['.index'] = n2;
		s2['.index'] = n1;

		this.state.reorder[conf] = true;

		return true;
	},

	save: function()
	{
		L.rpc.batch();

		var v = this.state.values;
		var n = this.state.creates;
		var c = this.state.changes;
		var d = this.state.deletes;

		var self = this;
		var snew = [ ];
		var pkgs = { };

		if (n)
			for (var conf in n)
			{
				for (var sid in n[conf])
				{
					var r = {
						config: conf,
						values: { }
					};

					for (var k in n[conf][sid])
					{
						if (k == '.type')
							r.type = n[conf][sid][k];
						else if (k == '.create')
							r.name = n[conf][sid][k];
						else if (k.charAt(0) != '.')
							r.values[k] = n[conf][sid][k];
					}

					snew.push(n[conf][sid]);

					self.callAdd(r.config, r.type, r.name, r.values);
				}

				pkgs[conf] = true;
			}

		if (c)
			for (var conf in c)
			{
				for (var sid in c[conf])
					self.callSet(conf, sid, c[conf][sid]);

				pkgs[conf] = true;
			}

		if (d)
			for (var conf in d)
			{
				for (var sid in d[conf])
				{
					var o = d[conf][sid];
					self.callDelete(conf, sid, (o === true) ? undefined : o);
				}

				pkgs[conf] = true;
			}

		return L.rpc.flush().then(function(responses) {
			/*
			 array "snew" holds references to the created uci sections,
			 use it to assign the returned names of the new sections
			*/
			for (var i = 0; i < snew.length; i++)
				snew[i]['.name'] = responses[i];

			return self.reorderSections();
		}).then(function() {
			pkgs = L.toArray(pkgs);

			self.unload(pkgs);

			return self.load(pkgs);
		});
	},

	apply: function(timeout)
	{
		var self = this;
		var date = new Date();
		var deferred = $.Deferred();

		if (typeof(timeout) != 'number' || timeout < 1)
			timeout = 10;

		self.callApply(timeout, true).then(function(rv) {
			if (rv != 0)
			{
				deferred.rejectWith(self, [ rv ]);
				return;
			}

			var try_deadline = date.getTime() + 1000 * timeout;
			var try_confirm = function()
			{
				return self.callConfirm().then(function(rv) {
					if (rv != 0)
					{
						if (date.getTime() < try_deadline)
							window.setTimeout(try_confirm, 250);
						else
							deferred.rejectWith(self, [ rv ]);

						return;
					}

					deferred.resolveWith(self, [ rv ]);
				});
			};

			window.setTimeout(try_confirm, 1000);
		});

		return deferred;
	},

	changes: L.rpc.declare({
		object: 'uci',
		method: 'changes',
		expect: { changes: { } }
	}),

	readable: function(conf)
	{
		return L.session.hasACL('uci', conf, 'read');
	},

	writable: function(conf)
	{
		return L.session.hasACL('uci', conf, 'write');
	}
});
