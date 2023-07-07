
//----------------------
// <auto-generated>
//     Generated REST API Client Code Generator v1.7.17.0 on 7/6/2023 11:32:08 PM
//     Using the tool Refitter v0.6.0
// </auto-generated>
//----------------------


using Refit;
using System.Collections.Generic;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace Chivalry2UnofficialServerBrowser
{
    public interface IServerBrowserAPI
    {
        [Post("/register")]
        Task<RegistrationResponse> Register([Body] ServerRegistrationRequest body);

        [Post("/heartbeat")]
        Task<RegistrationResponse> Heartbeat([Body] HeartbeatSignal body);

        [Get("/servers")]
        Task<ServerListResponse> Servers();


    }
}


//----------------------
// <auto-generated>
//     Generated using the NSwag toolchain v13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0)) (http://NSwag.org)
// </auto-generated>
//----------------------

#pragma warning disable 108 // Disable "CS0108 '{derivedDto}.ToJson()' hides inherited member '{dtoBase}.ToJson()'. Use the new keyword if hiding was intended."
#pragma warning disable 114 // Disable "CS0114 '{derivedDto}.RaisePropertyChanged(String)' hides inherited member 'dtoBase.RaisePropertyChanged(String)'. To make the current member override that implementation, add the override keyword. Otherwise add the new keyword."
#pragma warning disable 472 // Disable "CS0472 The result of the expression is always 'false' since a value of type 'Int32' is never equal to 'null' of type 'Int32?'
#pragma warning disable 612 // Disable "CS0612 '...' is obsolete"
#pragma warning disable 1573 // Disable "CS1573 Parameter '...' has no matching param tag in the XML comment for ...
#pragma warning disable 1591 // Disable "CS1591 Missing XML comment for publicly visible type or member ..."
#pragma warning disable 8073 // Disable "CS8073 The result of the expression is always 'false' since a value of type 'T' is never equal to 'null' of type 'T?'"
#pragma warning disable 3016 // Disable "CS3016 Arrays as attribute arguments is not CLS-compliant"
#pragma warning disable 8603 // Disable "CS8603 Possible null reference return"

namespace Chivalry2UnofficialServerBrowser
{
    using System = global::System;

    

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class HeartbeatSignal
    {
        /// <summary>
        /// The port number the server is running on
        /// </summary>

        [JsonPropertyName("port")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Port { get; set; }

        /// <summary>
        /// The number of players currently on the server
        /// </summary>

        [JsonPropertyName("player_count")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Player_count { get; set; }

        /// <summary>
        /// The max number of players the server allows
        /// </summary>

        [JsonPropertyName("max_players")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Max_players { get; set; }

        /// <summary>
        /// The current map being played on the server
        /// </summary>

        [JsonPropertyName("current_map")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Current_map { get; set; }

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class Mod
    {
        /// <summary>
        /// The name of the mod
        /// </summary>

        [JsonPropertyName("name")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Name { get; set; }

        /// <summary>
        /// The organization that provides the mod
        /// </summary>

        [JsonPropertyName("organization")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Organization { get; set; }

        /// <summary>
        /// The version of the mod
        /// </summary>

        [JsonPropertyName("version")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Version { get; set; }

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class ServerListResponse
    {
        /// <summary>
        /// A list of servers
        /// </summary>

        [JsonPropertyName("servers")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required]
        public ICollection<Server> Servers { get; set; } = new System.Collections.ObjectModel.Collection<Server>();

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class Server
    {
        /// <summary>
        /// The IP address of the server
        /// </summary>

        [JsonPropertyName("ip_address")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Ip_address { get; set; }

        /// <summary>
        /// The port number the server is running on
        /// </summary>

        [JsonPropertyName("port")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Port { get; set; }

        /// <summary>
        /// The name of the server
        /// </summary>

        [JsonPropertyName("name")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Name { get; set; }

        /// <summary>
        /// A description of the server
        /// </summary>

        [JsonPropertyName("description")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Description { get; set; }

        /// <summary>
        /// The current map being played on the server
        /// </summary>

        [JsonPropertyName("current_map")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Current_map { get; set; }

        /// <summary>
        /// The number of players currently on the server
        /// </summary>

        [JsonPropertyName("player_count")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Player_count { get; set; }

        /// <summary>
        /// The max number of players on the server
        /// </summary>

        [JsonPropertyName("max_players")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Max_players { get; set; }

        /// <summary>
        /// A list of mods running on the server
        /// </summary>

        [JsonPropertyName("mods")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required]
        public ICollection<Mod> Mods { get; set; } = new System.Collections.ObjectModel.Collection<Mod>();

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class ServerRegistrationRequest
    {
        /// <summary>
        /// The port number the server is running on
        /// </summary>

        [JsonPropertyName("port")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Port { get; set; }

        /// <summary>
        /// The name of the server
        /// </summary>

        [JsonPropertyName("name")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Name { get; set; }

        /// <summary>
        /// A description of the server
        /// </summary>

        [JsonPropertyName("description")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Description { get; set; }

        /// <summary>
        /// The current map being played on the server
        /// </summary>

        [JsonPropertyName("current_map")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        public string Current_map { get; set; }

        /// <summary>
        /// The number of players currently on the server
        /// </summary>

        [JsonPropertyName("player_count")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Player_count { get; set; }

        /// <summary>
        /// The max number of players on the server
        /// </summary>

        [JsonPropertyName("max_players")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        public int Max_players { get; set; }

        /// <summary>
        /// A list of mods running on the server
        /// </summary>

        [JsonPropertyName("mods")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required]
        public ICollection<Mod> Mods { get; set; } = new System.Collections.ObjectModel.Collection<Mod>();

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public partial class RegistrationResponse
    {
        /// <summary>
        /// Unix timestamp for when the server should refresh its registration. Only present if operation was successful
        /// </summary>

        [JsonPropertyName("refresh_before")]

        [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)]   
        public double Refresh_before { get; set; }

        /// <summary>
        /// Registration status of the server
        /// </summary>

        [JsonPropertyName("status")]

        [JsonIgnore(Condition = JsonIgnoreCondition.Never)]   
        [System.ComponentModel.DataAnnotations.Required(AllowEmptyStrings = true)]
        [JsonConverter(typeof(JsonStringEnumConverter))]
        public RegistrationResponseStatus Status { get; set; }

        private IDictionary<string, object> _additionalProperties;

        [JsonExtensionData]
        public IDictionary<string, object> AdditionalProperties
        {
            get { return _additionalProperties ?? (_additionalProperties = new Dictionary<string, object>()); }
            set { _additionalProperties = value; }
        }

    }

    [System.CodeDom.Compiler.GeneratedCode("NJsonSchema", "13.19.0.0 (NJsonSchema v10.9.0.0 (Newtonsoft.Json v13.0.3.0))")]
    public enum RegistrationResponseStatus
    {

        [System.Runtime.Serialization.EnumMember(Value = @"registered")]
        Registered = 0,

        [System.Runtime.Serialization.EnumMember(Value = @"banned")]
        Banned = 1,

    }


}

#pragma warning restore  108
#pragma warning restore  114
#pragma warning restore  472
#pragma warning restore  612
#pragma warning restore 1573
#pragma warning restore 1591
#pragma warning restore 8073
#pragma warning restore 3016
#pragma warning restore 8603
